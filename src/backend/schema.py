from pydantic import BaseModel, Field


class UserChat(BaseModel):
    """
    用户聊天对话请求
    """
    chat: str = Field(default="", description="用户查询问题")
    session_id: str = Field(default="", description="会话id")