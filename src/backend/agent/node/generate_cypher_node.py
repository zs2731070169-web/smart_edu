import logging

from langchain_core.output_parsers import StrOutputParser
from langgraph.runtime import Runtime
from neo4j_graphrag.retrievers.text2cypher import extract_cypher

from backend.agent.context import EnvContext
from backend.agent.state import OverallState
from backend.core.client.llm_client import llm_cypher
from backend.core.client.neo4j_client import graph_schema
from backend.prompts.gen_cypher_prompt import gen_cypher_prompt
from backend.utils.llm_retry_utils import acall_with_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


async def generate_cypher(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """根据用户问题与对齐实体生成 Cypher。校验失败回路时把上一轮错误反馈附在 question 末尾"""
    tid = runtime.context.get("thread_id", "-")
    question = state.get("question", "")
    aligned_entities = state.get("aligned_entities") or []
    validates = state.get("validates") or []

    # 纠错回路:把最近一次校验的错误信息追加到 question,促使模型修正
    if validates:
        last = validates[-1]
        if not last.is_correct:
            feedback = (
                f"\n\n上一轮生成的 Cypher 校验未通过,请根据反馈修正后重新生成:\n"
                f"- 错误信息:{last.errors}\n"
                f"- 改进建议:{last.suggestion}\n"
                f"- 上一轮 Cypher:{state.get('cypher', '')}"
            )
            question = question + feedback
            logger.info(f"[generate_cypher_node][{tid}] 检测到校验回路,已附加错误反馈到 prompt")

    chain = gen_cypher_prompt | llm_cypher | StrOutputParser()
    # Cypher 是主链路关键步骤,无法降级 — 失败直接抛 LLMServiceError 由 service 层兜底
    cypher = await acall_with_retry(
        lambda: chain.ainvoke({
            "schema": graph_schema,
            "entities": aligned_entities,
            "question": question
        }),
        op_name="generate_cypher",
    )

    cypher = extract_cypher(cypher)
    cypher = cypher[cypher.find("MATCH"):].strip()
    logger.info(f"[generate_cypher_node][{tid}] 生成cypher语句:{cypher}")

    return {"cypher": cypher}
