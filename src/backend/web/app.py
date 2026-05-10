import asyncio
import os

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from backend.config.settings import WEB_DIR, SESSION_SECRET_KEY, ROOT_PATH
from backend.web.api import route

app = FastAPI(root_path=ROOT_PATH)

# Session 数据不存储在服务器，而是加密后存在客户端 Cookie 里
# 每次http请求，SessionMiddleware都会读取Cookie里的session数据进行解密和反序列化，并挂载到request.session
# 每次http响应，SessionMiddleware会加密和序列化request.session，并写入Cookie中返回到客户端
# 首次执行session_id为空，会初始化session为 request.session = {}
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,  # HMAC 签名：每次http请求，用于session_id的加密和解密
    max_age=3600,
    https_only=False,
    same_site="lax"  # 允许用户从外部链接点击跳转到你的站点（顶层导航 GET）,阻止第三方页面通过 <img>、<iframe>、AJAX 等方式向你的站点发起请求, 阻断 CSRF 攻击
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=True,
)

# 加载静态资源（前端已分离）
# app.mount(path="/static", app=StaticFiles(directory=WEB_DIR, html=True), name="web")

app.include_router(route)

if __name__ == '__main__':
    # 端口从环境变量 APP_PORT 读取，默认 8000
    # 多节点部署时由 systemd 模板服务（smart_edu@.service）通过 Environment=APP_PORT=%i 注入
    port = int(os.environ.get('APP_PORT', 8080))
    # 直接调用 asyncio.run(server.serve()) 避免 uvicorn.run() 传递 loop_factory 参数
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
