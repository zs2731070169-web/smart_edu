import logging
from typing import AsyncGenerator

from langchain_core.messages import AIMessageChunk
from openai import BadRequestError

from backend.agent import graph
from backend.web.schema.schema import UserChat

logger = logging.getLogger(__name__)


class ChatService:
    """流式聊天服务,基于 LangGraph StateGraph 工作流编排"""

    async def retrieval_chat_stream(self, user_chat: UserChat) -> AsyncGenerator[str, None]:
        """逐 token 输出最终答复;仅 answer_node 内的 LLM 流被透传给客户端"""
        question = user_chat.chat
        session = user_chat.session_id

        if not question:
            logger.warning(f"聊天内容为空 - session_id: {session}")
            yield "抱歉,您还没有输入任何内容,请输入您的问题"
            return
        if not session:
            logger.warning(f"会话ID为空 - question: {question[:50]}")
            yield "抱歉,会话信息缺失,请刷新页面后重试"
            return

        try:

            async for chunk, metadata in graph.astream(
                    {
                        "messages": [{"role": "user", "content": question}],
                        "question": question,
                        "correct_count": 0,
                    },
                    config={"configurable": {"thread_id": session}},
                    context={"thread_id": session},
                    version="v2",
                    stream_mode="messages"
            ):
                # 如果是流式调用LLM输出的chunk，并且输出节点是answer，就进行流式输出
                if metadata["langgraph_node"] == "answer_node" and isinstance(chunk, AIMessageChunk) and chunk.content:
                    yield chunk.content
        except BadRequestError as e:
            logger.error(f"LLM 请求异常 - session_id: {session}, error: {e}")
            yield "抱歉,AI 服务暂时不可用,请稍后重试。"
        except Exception as e:
            logger.exception(f"工作流执行异常 - session_id: {session}, error: {e}")
            yield "抱歉,系统暂时无法处理该请求,请稍后再试。"
