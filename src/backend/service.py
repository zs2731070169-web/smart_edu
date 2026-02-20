from agent import gen_agent
from backend.schema import UserChat


class ChatService:

    def __init__(self):
        self.agent = gen_agent()

    async def chat(self, user_chat: UserChat) -> str:
        """
        聊天服务
        :param chat:
        """
        question = user_chat.chat
        session = user_chat.session_id

   

