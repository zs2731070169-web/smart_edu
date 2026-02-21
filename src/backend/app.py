import asyncio
import logging
import uuid

import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

from backend.schema import UserChat, QuestionReq
from backend.service import ChatService
from config.config import WEB_DIR

logging.basicConfig(format="%(asctime)s %(filename)s %(message)s", level=logging.INFO)
logger = logging.getLogger("Web")

root_path = "/smart/edu"
app = FastAPI(root_path=root_path)

# Session 数据不存储在服务器，而是加密后存在客户端 Cookie 里
# 每次http请求，SessionMiddleware都会读取Cookie里的session数据进行解密和反序列化，并挂载到request.session
# 每次http响应，SessionMiddleware会加密和序列化request.session，并写入Cookie中返回到客户端
# 首次执行session_id为空，会初始化session为 request.session = {}
app.add_middleware(
    SessionMiddleware,
    secret_key="lUtYVug40ycE7zdbGsx2JwrE7x2h6W",  # HMAC 签名：每次http请求，用于session_id的加密和解密
    max_age=3600,
    https_only=False,
    same_site="lax"  # 允许用户从外部链接点击跳转到你的站点（顶层导航 GET）,阻止第三方页面通过 <img>、<iframe>、AJAX 等方式向你的站点发起请求, 阻断 CSRF 攻击
)

# 加载静态资源
app.mount(path="/static", app=StaticFiles(directory=WEB_DIR, html=True), name="web")

# 对话服务
chat_service = ChatService()


@app.get("/")
async def index():
    return RedirectResponse(root_path + "/static/index.html")


@app.post("/new-chat")
async def new_chat(request: Request):
    """清除当前会话，下次发送消息时后端自动生成新的 session_id"""
    request.session.clear()
    return {"status": "ok"}


@app.post("/chat")
async def chat(question_req: QuestionReq, request: Request):
    """
    流式聊天服务，逐 token 推送最终答案
    :param question_req: 用户查询请求
    :param request: HTTP 请求（含 session）
    :return: 流式文本响应
    """
    # 获取 session
    session = request.session

    # 首次访问生成 session_id
    if "session_id" not in session:
        session['session_id'] = str(uuid.uuid4())
        logger.info(f"生成session_id: {session['session_id']}")

    return StreamingResponse(
        chat_service.retrieval_chat_stream(
            UserChat(question=question_req.question, session_id=session['session_id'])
        ),
        media_type="text/plain; charset=utf-8"
    )


if __name__ == '__main__':
    # 直接调用 asyncio.run(server.serve()) 避免 uvicorn.run() 传递 loop_factory 参数
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
