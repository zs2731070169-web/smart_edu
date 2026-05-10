import logging

from langchain_core.tools import tool
from pydantic import Field

from backend.config.settings import NODE_LIST
from backend.core.client.llm_client import llm_gpt
from backend.core.client.neo4j_client import graph
from backend.core.schema.schema import EntityPairs
from backend.prompts.extract_entities_prompt import extract_entities_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


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

    return llm_output
