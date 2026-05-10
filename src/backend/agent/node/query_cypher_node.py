import logging

from langgraph.runtime import Runtime

from backend.agent.context import EnvContext
from backend.agent.state import OverallState
from backend.core.client.neo4j_client import driver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("query_cypher")


async def query_cypher(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """执行 Cypher 并返回查询结果"""
    tid = runtime.context.get("thread_id", "-")
    cypher = state.get("cypher", "")
    logger.info(f"[query_cypher_node][{tid}] 入参 Cypher: {cypher}")

    try:
        records = driver.execute_query(query_=cypher).records
        results = [record.data() for record in records]
    except Exception as e:
        logger.error(f"[query_cypher_node][{tid}] 执行异常: {e}")
        results = []

    logger.info(f"[query_cypher_node][{tid}] 返回 {len(results)} 条结果: {results}")
    return {"query_results": results}
