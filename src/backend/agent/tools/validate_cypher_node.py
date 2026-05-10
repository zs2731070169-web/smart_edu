import logging
from typing import List

from neo4j.exceptions import CypherSyntaxError

from backend.agent.schema.schema import Entity, ValidateCypherResult
from backend.core.client.llm_client import llm_opus
from backend.core.client.neo4j_client import driver, graph_schema
from backend.prompts.cypher_validate_prompt import cypher_validate_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


# @tool(
#     name_or_callable="validate_cypher",
#     description="根据用户查询和原始Cypher语句, 对Cypher语句进行校验",
#     return_direct=False,
#     args_schema=ValidateCypher
# )
async def validate_cypher(cypher: str, question: str, entities: List[Entity]) -> ValidateCypherResult:
    """
    根据用户查询和原始Cypher语句, 对Cypher语句进行校验
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
