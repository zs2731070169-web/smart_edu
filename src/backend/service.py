import logging
from typing import AsyncGenerator

from openai import BadRequestError

from agent import gen_agent
from backend.schema import UserChat

logger = logging.getLogger(__name__)


class ChatService:

    def __init__(self):
        self.agent = None

    async def _get_agent(self):
        if not self.agent:
            self.agent = await gen_agent()
            logger.info("智能体已启动")

    def _reset_thread(self, session_id: str):
        """
        清除 InMemorySaver 中指定会话的损坏历史。
        当 tool_calls 消息写入后工具响应未能持久化时，历史会处于半残状态，
        后续携带该历史调用 LLM 会触发 400 Bad Request，需在此处清除后让用户重试。
        """
        try:
            checkpointer = getattr(self.agent, 'checkpointer', None)
            if checkpointer is None:
                return

            # InMemorySaver 内部以 thread_id 为第一层 key 存储 storage 和 writes
            cleared = False
            writes = getattr(checkpointer, 'writes', None)

            if isinstance(writes, dict) and session_id in writes:
                del writes[session_id]
                cleared = True

            if cleared:
                logger.info(f"已清除损坏会话历史 - session_id: {session_id}")
            else:
                logger.warning(f"未找到可清除的会话历史 - session_id: {session_id}")
        except Exception as e:
            logger.warning(f"清除会话历史失败 - session_id: {session_id}, error: {e}")

    async def retrieval_chat_stream(self, user_chat: UserChat) -> AsyncGenerator[str, None]:
        """
        流式聊天服务，逐 token 输出最终答案
        :param user_chat: 用户聊天请求
        :return: 异步文本 token 生成器
        """
        question = user_chat.chat
        session = user_chat.session_id

        # 参数校验
        if not question:
            logger.warning(f"聊天内容为空 - session_id: {session}")
            yield "抱歉，您还没有输入任何内容，请输入您的问题"
            return
        if not session:
            logger.warning(f"会话ID为空 - question: {question[:50]}")
            yield "抱歉，会话信息缺失，请刷新页面后重试"
            return

        # 获取agent
        await self._get_agent()

        try:
            # 流式执行智能体，过滤出 agent 节点（编排 LLM）的最终回答 token
            # langgraph_node == "agent" 确保只取智能体自身输出，排除工具内部的 LLM 调用
            async for event in self.agent.astream_events(
                    {"messages": [{"role": "user", "content": question}]},
                    config={"configurable": {"thread_id": session}},
                    version="v2"  # 使用v2版本的事件结构
            ):
                if (event["event"] == "on_chat_model_stream"
                        and event.get("metadata", {}).get("langgraph_node") == "model"):
                    chunk = event["data"]["chunk"]
                    # content 为空时是工具调用决策 token，有内容时才是正式回答
                    if chunk.content:
                        yield chunk.content
        except BadRequestError as e:
            error_msg = str(e)
            # tool_calls 历史损坏：assistant 消息含 tool_calls 但缺少对应 tool 响应消息
            if "tool_call" in error_msg and "tool messages" in error_msg:
                logger.error(
                    f"会话历史损坏（tool_calls 无对应响应），自动重置 - "
                    f"session_id: {session}, error: {e}"
                )
                self._reset_thread(session)
                yield "抱歉，上一轮对话异常中断导致会话历史损坏，已自动重置。请重新提问。"
            else:
                logger.error(f"LLM 请求异常 - session_id: {session}, error: {e}")
                yield "抱歉，AI 服务暂时不可用，请稍后重试。"
