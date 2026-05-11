import logging

from langgraph.runtime import Runtime

from backend.agent.context import EnvContext
from backend.agent.schema.schema import IntentResult
from backend.agent.state import OverallState
from backend.core.client.llm_client import llm_chat
from backend.core.error import LLMServiceError
from backend.prompts.intent_prompt import intent_prompt
from backend.utils.history_utils import compress_history
from backend.utils.llm_retry_utils import acall_with_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("intent_identify")


async def intent_identify(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """意图识别节点:分三类(业务无关 / 对话型 / 知识查询)"""
    tid = runtime.context.get("thread_id", "-")
    messages = state.get("messages") or []
    question = messages[-1].content if messages else state.get("question", "")
    logger.info(f"[intent_node][{tid}] 入参 question='{question}'")

    if not question:
        return {
            "question": "",
            "is_relevant": False,
            "intent_reply": "您好,请输入您的问题,我会尽力为您解答教育相关内容。",
        }

    # 压缩历史对话
    history = compress_history(messages[:-1])

    # 执行意图识别
    prompt = intent_prompt.invoke({"question": question, "history": history})
    try:
        result: IntentResult = await acall_with_retry(
            lambda: llm_chat.with_structured_output(IntentResult, method="function_calling").ainvoke(prompt),
            op_name="intent",
        )
    except LLMServiceError as e:
        # 降级:意图判定失败时按「知识查询」处理,把问题原样交给下游主链路兜底(判定失败不阻断对话，降级为知识查询)
        logger.warning(
            f"[intent_node][{tid}] LLM 失败降级为知识查询: reason={e.classified.reason.value}"
        )
        return {
            "question": question,
            "is_relevant": True,
            "intent_reply": "",
        }

    logger.info(
        f"[intent_node][{tid}] 结果: is_relevant={result.is_relevant}, "
        f"direct_reply='{result.direct_reply[:60]}...'"
    )

    # 仅写分类信号到 state,最终回复统一由 answer_node 流式输出
    return {
        "question": question,
        "is_relevant": result.is_relevant,
        "intent_reply": result.direct_reply,
    }
