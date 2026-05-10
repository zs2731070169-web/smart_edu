import logging
import uuid
from urllib.request import Request

from fastapi import APIRouter
from starlette.responses import RedirectResponse, StreamingResponse

from backend.service import chat_service
from backend.web.app import root_path
from backend.web.schema import QuestionReq, UserChat

logging.basicConfig(format="%(asctime)s %(filename)s %(message)s", level=logging.INFO)
logger = logging.getLogger("Web")
logging.getLogger("uvicorn.access").addFilter(
    lambda record: "socket.io" not in record.getMessage()
)

route = APIRouter()


# 本地测试开发使用, 生产环境无效，生产环境走 nginx 代理
@route.get("/")
async def index():
    return RedirectResponse(root_path + "/static/index.html")


@route.post("/new-chat")
async def new_chat(request: Request):
    """清除当前会话，下次发送消息时后端自动生成新的 session_id"""
    request.session.clear()  # 清除cookie里所有残留session数据，返回给客户端空session
    return {"status": "ok"}


@route.post("/chat")
async def chat(question_req: QuestionReq, request: Request):
    """
    流式聊天服务，逐 token 推送最终答案
    :param question_req: 用户查询请求
    :param request: HTTP 请求（含 session）
    :return: 流式文本响应
    """
    # 获取 session
    session = request.session

    # 首次访问生成新的session_id
    if "session_id" not in session:
        session['session_id'] = str(uuid.uuid4())  # 为首次访问用户生成唯一的session_id
        logger.info(f"首次访问，生成session_id: {session['session_id']}")

    return StreamingResponse(
        chat_service.retrieval_chat_stream(
            UserChat(question=question_req.question, session_id=session['session_id'])
        ),
        media_type="text/plain; charset=utf-8"
    )
