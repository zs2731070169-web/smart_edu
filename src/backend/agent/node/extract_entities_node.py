import logging

from langgraph.runtime import Runtime

from backend.agent.context import EnvContext
from backend.agent.schema.schema import EntityPairs
from backend.agent.state import OverallState
from backend.config.settings import NODE_LIST
from backend.core.client.llm_client import llm_extract
from backend.core.client.neo4j_client import graph
from backend.prompts.extract_entities_prompt import extract_entities_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("extract_entities")


async def extract_entities(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """从用户查询里抽取实体,并返回实体和相关图标签列表"""
    tid = runtime.context.get("thread_id", "-")
    question = state.get("question", "")
    logger.info(f"[extract_entities_node][{tid}] 入参 question='{question}'")

    if not graph.get_structured_schema['node_props']:
        logger.info(f"[extract_entities_node][{tid}] 图 schema 为空,跳过抽取")
        return {"entity_pairs": []}

    prompt = extract_entities_prompt.invoke({"question": question, "schema": NODE_LIST})
    llm_output: EntityPairs = await (
        llm_extract
        .with_structured_output(schema=EntityPairs, method="function_calling")
        .ainvoke(prompt)
    )

    logger.info(f"[extract_entities_node][{tid}] 结果: {llm_output.entity_pairs}")
    return {"entity_pairs": llm_output.entity_pairs}
