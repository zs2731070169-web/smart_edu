from pydantic import BaseModel, Field


class UserChat:
    """
    用户聊天对话请求
    """

    def __init__(self, question: str, session_id: str):
        self.chat: str = question
        self.session_id: str = session_id


class QuestionReq(BaseModel):
    question: str = Field(default="", description="用户查询请求")
