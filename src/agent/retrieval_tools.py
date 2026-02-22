import asyncio
import logging
from typing import List, Tuple

from langchain_core.tools import tool
from neo4j import Query
from neo4j.exceptions import CypherSyntaxError
from pydantic import Field

from agent.context import thread_pool_executor, embedding_model, driver, graph_schema, llm_opus, graph, \
    llm_gpt
from agent.prompts import cypher_validate_prompt, extract_entities_prompt
from agent.schema import EntityPairs, Entity, ValidateCypherResult, ValidateCypher
from config.config import NODE_LIST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


# 获取设备
# device = "cuda" if torch.cuda.is_available() else "cpu"

# 加载实体抽取模型
# nlp_deberta_tokenizer = AutoTokenizer.from_pretrained(NLP_DEBERTA_MODEL)
# nlp_deberta_model = AutoModelForTokenClassification.from_pretrained(NLP_DEBERTA_MODEL).to(device)
# nlp_deberta_model.eval()


@tool(
    name_or_callable="extract_entities",
    description="从用户查询里抽取实体，并返回实体和相关图标签列表",
    return_direct=False
)
async def extract_entities(question: str = Field(default="", description="用户问题")) -> EntityPairs:
    """
    执行实体抽取工具
    :param question:
    :return:
    """
    logger.info(f"[实体抽取] 入参 question='{question}'")

    prompt = extract_entities_prompt.invoke({"question": question, "schema": NODE_LIST})

    if not graph.get_structured_schema['node_props']:
        logger.info("[实体抽取] 图 schema 为空，跳过抽取")
        return EntityPairs()

    llm_output = await (llm_gpt
                        .with_structured_output(schema=EntityPairs)
                        .ainvoke(prompt))

    logger.info(f"[实体抽取] 结果: {llm_output.entity_pairs}")

    return llm_output.entity_pairs


@tool(
    name_or_callable="entities_align_async",
    description="通过混合检索进行实体对齐，并返回对齐后的实体和标签对列表",
    args_schema=EntityPairs,
    return_direct=False,
)
async def entities_align_async(entity_pairs: EntityPairs) -> List[Tuple[str, str]]:
    """
    实体对齐工具
    :param entity_pairs:
    :return:
    """
    logger.info(f"[实体对齐] 入参 entity_pairs={entity_pairs}")

    if not entity_pairs:
        logger.info("[实体对齐] 实体列表为空，跳过对齐")
        return []

    # 分别获取实体列表和标签列表
    entity_pairs = [(entity_pair.entity, entity_pair.label) for entity_pair in entity_pairs]
    entities, labels = zip(*entity_pairs)

    search_targets = [(entity, label)
                      for entity, label in zip(entities, labels)
                      if label not in ["Teacher", "Student", "Price"]
                      ]
    logger.info(f"[实体对齐] 过滤后待检索实体: {search_targets}")

    # 异步并发执行混合检索
    hybrid_search_results = await asyncio.gather(*[
        asyncio.wrap_future(
            thread_pool_executor.submit(
                _search_entity, entity=entity, label=label, top_k=1
            )
        ) for entity, label in search_targets
    ])

    # 收集对齐后的实体列表
    aligned_entities = [
        (result[0]['text'], result[0]['labels'][0])
        for result in hybrid_search_results
        if result  # 过滤掉低于阈值的空检索结果
    ]

    logger.info(f"[实体对齐] 结果: {aligned_entities}")

    return aligned_entities


def _search_entity(entity: str,
                   label: str,
                   top_k: int = 3,
                   alpha: float = 0.5,
                   threshold: float = 0.5
                   ) -> list:
    """
    对单个实体进行线性混合检索
    :param entity: 实体文本
    :param label: 实体标签，用于确定检索索引
    :param top_k: 返回结果数量
    :param alpha: 向量检索权重，全文检索权重为 (1 - alpha)
    :return: 检索结果列表
    """
    logger.info(
        f"[混合检索] 入参 entity='{entity}', label='{label}', top_k={top_k}, alpha={alpha}, threshold={threshold}")

    # 生成实体向量
    query_vector = embedding_model.embed_query(entity)

    # 定义索引名称：{label}_vector_index / {label}_fulltext_index
    label_lower = label.lower()
    vector_index_name = f"{label_lower}_vector_index"
    fulltext_index_name = f"{label_lower}_fulltext_index"
    logger.info(f"[混合检索] 使用索引: vector='{vector_index_name}', fulltext='{fulltext_index_name}'")

    # 使用 get_search_query 构建混合检索 Cypher
    query = (
        """
        CALL {
            CALL db.index.vector.queryNodes($vector_index_name, $top_k * $effective_search_ratio, $query_vector)
            YIELD node, score
            WITH node, score LIMIT $top_k
            WITH collect({node: node, score: score}) AS nodes
            UNWIND nodes AS n
            WITH n.node AS node, n.score AS score
            RETURN node, score * $alpha AS score
            UNION
            CALL db.index.fulltext.queryNodes($fulltext_index_name, $query_text, {limit: $top_k})
            YIELD node, score
            WITH collect({node: node, score: score}) AS nodes, max(score) AS ft_index_max_score
            UNWIND nodes AS n
            WITH n.node AS node, (n.score / ft_index_max_score) AS rawScore
            RETURN node, rawScore * (1 - $alpha) AS score
        }
        WITH node, sum(score) AS score ORDER BY score DESC LIMIT $top_k
        RETURN node.`name` AS text, labels(node) AS labels, score, node {.*, `name`: Null, `embedding`: Null, id: Null } AS metadata
        """
    )

    # 合并运行时参数
    run_params = {
        "vector_index_name": vector_index_name,
        "query_vector": query_vector,
        "fulltext_index_name": fulltext_index_name,
        "query_text": entity,
        "top_k": top_k,
        "effective_search_ratio": 1,
        "alpha": alpha,
    }

    # 进行混合检索
    with driver.session() as session:
        result = session.run(Query(text=query), run_params)
        records = result.data()

    logger.info(f"[混合检索] 原始结果({len(records)}条): {records}")

    # 判断检索结果是否达到期望阈值
    retrieval_records = [record for record in records if record['score'] >= threshold]
    logger.info(f"[混合检索] 阈值过滤后({len(retrieval_records)}条): {retrieval_records}")

    return retrieval_records


# @tool(
#     name_or_callable="gen_cypher",
#     description="根据用户查询和抽取的实体对构建查询Cypher语句",
#     return_direct=False,
#     args_schema=GenCypher
# )
# async def gen_cypher(question: str, entities: List[Entity]) -> str:
#     """
#     构建cypher
#     :param question: 用户查询
#     :param entities: 提取的实体
#     :return: cypher查询语句
#     """
#     # 构建执行链
#     chain = gen_cypher_prompt | llm_opus | StrOutputParser()
#
#     # 生成cypher
#     cypher = await chain.ainvoke({"schema": graph_schema, "entities": entities, "question": question})
#
#     # 精确提取可执行Cypher语句
#     cypher = extract_cypher(cypher)
#     cypher = cypher[cypher.find("MATCH"):].strip()
#
#     logger.info("生成cypher语句:%s" % cypher)
#
#     return cypher


@tool(
    name_or_callable="validate_cypher",
    description="根据用户查询和原始Cypher语句, 对Cypher语句进行校验",
    return_direct=False,
    args_schema=ValidateCypher
)
async def validate_cypher(cypher: str, question: str, entities: List[Entity]) -> ValidateCypherResult:
    """
    校验cypher
    :param: cypher: cypher语句
    :param question: 用户查询
    :param entities: 提取的实体
    :return: 校验结果
    """
    logger.info(f"[Cypher校验] 入参 question='{question}', entities={entities}")
    logger.info(f"[Cypher校验] 待校验 Cypher: {cypher}")

    # 校验语法错误
    errors = ""
    try:
        driver.execute_query(query_=f"EXPLAIN {cypher}")
        logger.info("[Cypher校验] 语法校验通过")
    except CypherSyntaxError as e:
        errors = str(e)
        logger.warning(f"[Cypher校验] 语法错误: {errors}")

    # 校验提示词
    prompt = cypher_validate_prompt.format_messages(
        cypher=cypher, question=question, entities=entities, schema=graph_schema)

    # 执行校验（使用 function_calling 而非 json_schema，避免代理不支持 response_format）
    llm_output: ValidateCypherResult = await (llm_opus
                                              .with_structured_output(ValidateCypherResult, method="function_calling")
                                              .ainvoke(prompt))

    # 将语法错误合并进 LLM 返回的错误列表
    if errors:
        llm_output.errors.append({"语法错误": errors})
        llm_output.is_correct = False

    logger.info(f"[Cypher校验] 结果: is_correct={llm_output.is_correct}, errors={llm_output.errors}")

    return llm_output


@tool(
    name_or_callable="query_cypher",
    description="执行Cypher语句并返回查询结果",
    return_direct=False
)
def query_cypher(cypher: str = Field(default="", description="cypher语句")) -> str:
    """
    执行cypher
    :param: cypher: cypher语句
    :return: 返回执行结果
    """
    logger.info(f"[图查询] 入参 Cypher: {cypher}")
    results = driver.execute_query(query_=cypher).records
    logger.info(f"[图查询] 返回 {len(results)} 条结果: {results}")
    return results


if __name__ == '__main__':
    pass
    # question = "张老师的大数据和java课程"
    # llm_output = extract_entities(question)  # 抽取实体
    # entities = asyncio.run(entities_align(llm_output))  # 实体对齐
    # cypher = gen_cypher(question, entities)  # 生成cypher

# @tool(
#     name="实体抽取",
#     description="从输入的文本中抽取实体，并返回实体列表"
# )
# def extract_entity(question: str) -> str:
#     """
#     执行实体抽取工具
#     :param question:
#     :return:
#     """
#
#     # 基础模型加载
#     inputs = nlp_deberta_tokenizer(
#         question,
#         padding=True,
#         return_tensors="pt"
#     )
#     # 模型输入加载到GPU
#     inputs_tensor = {k: v.to(device) for k, v in inputs.items()}
#     # 执行模型推理
#     with torch.no_grad():
#         outputs = nlp_deberta_model(**inputs_tensor)
#
#     print(outputs.logits)
#     # 获取模型预测结果
#     """
#     batch_size:指的是一次模型前向传播中输入的句子数量
#     sequence_length:一句话的token数量
#     num_labels：每个token的分数列表，维度对齐
#     (batch_size=1, sequence_length=4, num_labels=3)
#     [
#       [   # 第一句话
#         [类别1分数, 类别2分数, 类别3分数],  ← token1
#         [类别1分数, 类别2分数, 类别3分数],  ← token2
#         [类别1分数, 类别2分数, 类别3分数],  ← token3
#         [类别1分数, 类别2分数, 类别3分数],  ← token4
#       ]
#     ]
#     (2, 4, 3)
#     [
#       [  # 第1句话
#         [x,x,x],
#         [x,x,x],
#         [x,x,x],
#         [x,x,x],
#       ],
#       [  # 第2句话
#         [x,x,x],
#         [x,x,x],
#         [x,x,x],
#         [x,x,x],
#       ]
#     ]
#     """
#     # 获取最后一个维度（每个token的分数列表）的最大分数
#     model_predictions = outputs.logits.argmax(dim=-1).tolist()
#     final_predictions = []
#     entity = ""
#     # 遍历输入和预测结果
#     for tokens, prediction in zip(question, model_predictions[0]):
#         if 0 not in model_predictions[0]:
#             final_predictions.append(entity)
#         elif prediction == 1:
#             entity += tokens
#         elif prediction == 0:
#             final_predictions.append(entity)
#             entity = ""
#
#
#     print(final_predictions)
