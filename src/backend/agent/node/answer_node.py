import logging

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from backend.agent.context import EnvContext
from backend.agent.state import OverallState
from backend.config.constants import MAX_CORRECT_LOOPS
from backend.core.client.llm_client import llm_chat
from backend.core.error import classify_llm_error
from backend.prompts.answer_prompt import direct_reply_system_prompt, max_correct_system_prompt, \
    empty_results_system_prompt, answer_system_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("answer")


async def answer(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """生成最终答复(流式 token 自动经 LangGraph astream_events 冒泡到外层)"""
    tid = runtime.context.get("thread_id", "-")
    messages = _build_messages(state)
    logger.info(f"[answer_node][{tid}] 准备生成,分支判定完成,system 提示长度={len(messages[0].content)}")

    # 流式调用不做重试(中途断流难续传),失败直接以用户文案兜底,保证用户始终有响应
    try:
        chunks = []
        # service种chat流式输出想要将answer输出的token逐token返回，那么answer节点对llm的调用必须用astream来配合
        async for chunk in llm_chat.astream(messages):
            if chunk.content:
                chunks.append(chunk.content)
        final_answer = "".join(chunks)
    except Exception as e:
        classified = classify_llm_error(e)
        final_answer = classified.user_message
        logger.warning(
            f"[answer_node][{tid}] 流式生成失败 reason={classified.reason.value} "
            f"status={classified.status_code} — 返回兜底文案"
        )
    logger.info(f"[answer_node][{tid}] 生成完成,长度={len(final_answer)}")

    return {"messages": [AIMessage(content=final_answer)]}


def _build_messages(state: OverallState) -> list:
    """根据 state 选择不同提示词:意图直答转述 / 校验失败兜底 / 空结果兜底 / 正常回答"""
    question = state.get("question", "")
    intent_reply = state.get("intent_reply") or ""
    correct_count = state.get("correct_count", 0) or 0
    validates = state.get("validates") or []
    query_results = state.get("query_results")

    # 1. 意图直答(业务无关 / 对话型)
    is_direct = not state.get("is_relevant")
    if is_direct and intent_reply:
        return [SystemMessage(content=direct_reply_system_prompt), HumanMessage(content=intent_reply)]

    # 2. 校验回路超限仍未通过
    last_invalid = validates and not validates[-1].is_correct
    if correct_count >= MAX_CORRECT_LOOPS and last_invalid:
        return [SystemMessage(content=max_correct_system_prompt), HumanMessage(content=question)]

    # 3. 查询结果为空
    if not query_results:
        return [SystemMessage(content=empty_results_system_prompt), HumanMessage(content=question)]

    # 4. 正常回答:整合查询结果
    user_text = f"用户问题:{question}\n查询结果:{query_results}"
    return [SystemMessage(content=answer_system_prompt), HumanMessage(content=user_text)]
