import asyncio
import logging
from typing import List, Tuple

from langchain_core.tools import tool
from neo4j import Query

from backend.core.client.llm_client import embedding_model
from backend.core.client.neo4j_client import driver
from backend.agent.schema import EntityPairs, Entity
from backend.utils.thread_utils import thread_pool_executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


# @tool(
#     name_or_callable="entities_align",
#     description="通过混合检索进行实体对齐，并返回对齐后的实体和标签对列表",
#     args_schema=EntityPairs,
#     return_direct=False,
# )
async def entities_align(entity_pairs: List[Entity]) -> List[Tuple[str, str]]:
    """
    通过混合检索进行实体对齐，并返回对齐后的实体和标签对列表
    :param entity_pairs: 实体列表（由 args_schema=EntityPairs 解包后直接传入）
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
