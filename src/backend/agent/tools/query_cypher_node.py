import logging

from pydantic import Field

from backend.core.client.neo4j_client import driver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


# @tool(
#     name_or_callable="query_cypher",
#     description="执行Cypher语句并返回查询结果",
#     return_direct=False
# )
def query_cypher(cypher: str = Field(default="", description="cypher语句")) -> str:
    """
    执行Cypher语句并返回查询结果
    :param: cypher: cypher语句
    :return: 返回执行结果
    """
    logger.info(f"[图查询] 入参 Cypher: {cypher}")
    results = driver.execute_query(query_=cypher).records
    logger.info(f"[图查询] 返回 {len(results)} 条结果: {results}")
    return results
