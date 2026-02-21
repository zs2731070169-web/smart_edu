import logging
from typing import AsyncGenerator

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

        # 流式执行智能体，过滤出 agent 节点（编排 LLM）的最终回答 token
        # langgraph_node == "agent" 确保只取智能体自身输出，排除工具内部的 LLM 调用
        async for event in self.agent.astream_events(
                {"messages": [{"role": "user", "content": question}]},
                config={"configurable": {"thread_id": session}},
                version="v2" # 使用v2版本的事件结构
        ):
            if (event["event"] == "on_chat_model_stream"
                    and event.get("metadata", {}).get("langgraph_node") == "model"):
                chunk = event["data"]["chunk"]
                # content 为空时是工具调用决策 token，有内容时才是正式回答
                if chunk.content:
                    yield chunk.content
