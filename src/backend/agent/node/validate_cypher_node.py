import logging

from langgraph.runtime import Runtime
from neo4j.exceptions import CypherSyntaxError

from backend.agent.context import EnvContext
from backend.agent.schema.enums import ErrorTypes
from backend.agent.schema.schema import ValidateCypherResult
from backend.agent.state import OverallState
from backend.core.client.llm_client import llm_cypher
from backend.core.client.neo4j_client import driver, graph_schema
from backend.prompts.cypher_validate_prompt import cypher_validate_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("validate_cypher")


async def validate_cypher(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """对 Cypher 进行语法 + 语义双重校验,失败则交回 generate_cypher 纠错"""
    tid = runtime.context.get("thread_id", "-")
    cypher = state.get("cypher", "")
    question = state.get("question", "")
    aligned_entities = state.get("aligned_entities") or []
    correct_count = state.get("correct_count", 0) or 0

    logger.info(f"[validate_cypher_node][{tid}] 入参 question='{question}', entities={aligned_entities}")
    logger.info(f"[validate_cypher_node][{tid}] 待校验 Cypher: {cypher}")

    # 语法校验
    try:
        driver.execute_query(query_=f"EXPLAIN {cypher}")
        logger.info(f"[validate_cypher_node][{tid}] 语法校验通过")
    except CypherSyntaxError as e:
        logger.warning(f"[validate_cypher_node][{tid}] 语法错误: {str(e)}")
        return {
            "validates": [
                ValidateCypherResult(
                    errors=[{"语法错误": str(e)}],
                    is_correct=False,
                    error_type=ErrorTypes.SYNTAX)
            ],
            "correct_count": correct_count + 1,
        }

    # 语义校验(LLM)
    prompt = cypher_validate_prompt.format_messages(
        cypher=cypher, question=question, entities=aligned_entities, schema=graph_schema)
    validate_result: ValidateCypherResult = await (
        llm_cypher
        .with_structured_output(ValidateCypherResult, method="function_calling")
        .ainvoke(prompt)
    )

    logger.info(
        f"[validate_cypher_node][{tid}] 结果: is_correct={validate_result.is_correct}, errors={validate_result.errors}")

    return {
        "validates": [validate_result],  # 追加到历史
        "correct_count": correct_count + 1,
    }
