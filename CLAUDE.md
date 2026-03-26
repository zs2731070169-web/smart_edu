# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

AI 驱动的智能教育系统，基于 **RAG + 知识图谱**架构，提供自然语言智能问答服务。用户通过 Web 界面提问，后端 Agent 自动完成实体抽取→实体对齐→Cypher 生成→图查询→流式回答的完整链路。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务（在项目根目录下执行，默认端口 8000）
cd src && python -m backend.web.api.app
# 指定端口（多节点场景）
APP_PORT=8001 cd src && python -m backend.web.api.app

# 直接测试 Agent（运行 backend/core/agent/__init__.py 中的 main()）
cd src && python -m backend.core.agent

# 数据同步：MySQL → Neo4j（首次部署或数据变更后执行，需要 GPU）
cd src && python -m backend.sync.cli.sync_cli

# UIE 模型微调 / 评估 / 标注数据转换
cd uie_pytorch && python finetune.py
cd uie_pytorch && python evaluate.py
cd uie_pytorch && python doccano.py
```

## 核心架构

### 请求处理流程

```
Web UI → POST /smart/edu/chat
  → ChatService.retrieval_chat_stream()  (src/backend/service/service.py)
  → Agent.astream_events()              (src/backend/core/agent/__init__.py)
  → 流式返回 token（仅过滤 langgraph_node == "model" 的输出）
```

Agent 在 `ChatService` 中**懒加载**：`_get_agent()` 在首次请求时调用 `gen_agent()` 初始化，之后复用同一实例。流式事件通过 `astream_events(version="v2")` 产生，只有 `event["metadata"]["langgraph_node"] == "model"` 的事件才会 `yield` 给客户端，工具调用的中间输出被过滤。

### Agent 工作链（LangGraph ReAct）

`gen_agent()` 在 `src/backend/core/agent/__init__.py` 中构建 LangGraph ReAct Agent：

1. **意图判断**：对话型直接回答，业务无关问题拒绝，知识查询继续后续步骤
2. **实体抽取** (`extract_entities`)：`llm_gpt` 从问题中识别实体和标签（基于 `NODE_LIST`）
3. **实体对齐** (`entities_align_async`)：混合检索（向量 + 全文）将用户实体对齐到图数据库节点；`Teacher`、`Student`、`Price` 三类被显式跳过
4. **Cypher 生成**：Agent 主 LLM（`llm_gpt`）根据图 schema 和对齐实体直接生成 Cypher
5. **Cypher 校验** (`validate_cypher`)：`llm_opus` 语义校验 + Neo4j `EXPLAIN` 语法校验，失败则纠错重试
6. **图查询** (`query_cypher`)：执行 Cypher，返回 JSON 结果
7. **自然语言回答**：整合结果，流式输出给用户

### 混合检索原理

`src/backend/core/tools/retrieval_tools.py` 的 `_search_entity()` 在线程池中执行同步 Neo4j 查询，通过 `asyncio.wrap_future` 并发调度多个实体：

```
score = vector_score * alpha + fulltext_score * (1 - alpha)
# alpha 默认 0.5，threshold 默认 0.5
```

- 向量索引命名规范：`{label_lower}_vector_index`
- 全文索引命名规范：`{label_lower}_fulltext_index`（CJK 分析器）

### 全局单例初始化（分层 client 模块）

运行时全局对象拆分到两个 client 模块，在**模块导入时**立即初始化（非懒加载）：

**`src/backend/core/client/llm_client.py`**

| 对象 | 说明 |
|------|------|
| `embedding_model` | 本地 `bge-base-zh-v1.5`（768 维，cosine），混合检索向量部分 |
| `llm_gpt` | `gpt-5.2`（CLOSEAI），实体抽取和 Agent 主 LLM |
| `llm_opus` | `claude-opus-4-6`（CLOSEAI），Cypher 校验专用 |

**`src/backend/core/client/neo4j_client.py`**

| 对象 | 说明 |
|------|------|
| `driver` | Neo4j 原生驱动（`GraphDatabase.driver`），执行 Cypher 和混合检索 |
| `graph` | LangChain `Neo4jGraph`，获取图 schema |
| `graph_schema` | `graph.schema`，注入 Agent 系统提示词 |

**`src/backend/utils/thread_utils.py`**

| 对象 | 说明 |
|------|------|
| `thread_pool_executor` | `ThreadPoolExecutor(max_workers=10)`，混合检索并发调度 |

### 模块职责

| 路径 | 职责 |
|------|------|
| `src/backend/web/api/app.py` | FastAPI 入口，SessionMiddleware，路由定义，静态文件挂载 |
| `src/backend/service/service.py` | 流式聊天服务，Agent 懒加载，过滤中间节点输出 |
| `src/front/` | 前端静态资源：`index.html`、`chat.js`（ES module）、`chat.css` |
| `src/backend/core/agent/__init__.py` | LangGraph ReAct Agent 构建，`gen_agent()` |
| `src/backend/core/client/llm_client.py` | 全局单例：LLM 模型、embedding 模型 |
| `src/backend/core/client/neo4j_client.py` | 全局单例：Neo4j driver、graph、graph_schema |
| `src/backend/core/tools/retrieval_tools.py` | 4 个 LangChain 工具：实体抽取、对齐、Cypher 校验、图查询 |
| `src/backend/prompts/prompts.py` | 系统提示词（含完整 schema 和约束规则）、各工具提示词 |
| `src/backend/core/schema/schema.py` | Pydantic 模型：`Entity`、`EntityPairs`、`ValidateCypherResult` 等 |
| `src/backend/web/schema/schema.py` | Web 层 Pydantic 模型：`UserChat`、`QuestionReq` |
| `src/backend/config/settings.py` | 所有配置项，支持 `.env` 覆盖 |
| `src/backend/core/db/db_conn.py` | `MysqlReader`（上下文管理器，供数据同步使用） |
| `src/backend/core/db/neo_conn.py` | `Neo4jWriter`（Neo4j 连接管理，含 embedding 模型，供 Repo 使用） |
| `src/backend/repositories/neo_repo.py` | `Neo4jRepo`：Neo4j CRUD 操作（节点/关系/索引创建），支持上下文管理器 |
| `src/backend/sync/cli/sync_cli.py` | MySQL → Neo4j 数据同步，UIE 知识点抽取（需 GPU），索引创建 |
| `src/backend/sync/schema/schema.py` | 同步相关 Pydantic 模型：`Node`、`NodeRelation`、`VectorIndex`、`FullIndex` |
| `src/backend/utils/thread_utils.py` | 全局线程池，供混合检索并发调度使用 |
| `uie_pytorch/` | UIE 通用信息抽取模型，支持 ONNX 和 PyTorch 后端 |

## 配置说明

所有配置集中在 `src/backend/config/settings.py`，通过 `.env` 文件覆盖（参考 `.env.example`）：

- **LLM**：`llm_gpt`（`gpt-5.2`）和 `llm_opus`（`claude-opus-4-6`）均使用 `CLOSEAI_CONFIG`
- **Neo4j**：`NEO4J_URI` 默认 `neo4j://localhost:7687`
- **MySQL**：`MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`
- **嵌入模型**：`models/bge-base-zh-v1.5`（本地 HuggingFace，768 维）
- **UIE 模型**：`models/uie_base_pytorch`，微调最优检查点在 `checkpoint/model_best/`
- **`AGENT_WITH_MEMORY`**：是否启用跨轮对话记忆（`InMemorySaver`），默认 `true`
- **`APP_PORT`**：服务监听端口，默认 `8000`；多节点部署时由 systemd 模板注入
- **`NODE_LIST`**：`['Course', 'Chapter', 'Question', 'Knowledge', 'Category', 'Paper', 'Subject', 'Video']`

## 部署

### 服务管理（Systemd 模板）

`deploy/sys/smart_edu@.service` 为多节点模板服务，`%i` 为实例标识符（即端口号）：

```bash
# 部署两个节点
cp deploy/sys/smart_edu@.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable smart_edu@8000 smart_edu@8001
systemctl start smart_edu@8000 smart_edu@8001

# 查看各节点日志（SyslogIdentifier 不同）
journalctl -u smart_edu@8000 -f
journalctl -u smart_edu@8001 -f
```

### Nginx（动静分离 + 负载均衡）

`deploy/nginx/nginx.conf` 核心设计：

- **动静分离**：`/smart/edu/static/` 由 Nginx 直接从磁盘服务（`alias /opt/smart_edu/src/front/`），不经过 Python 后端；API 请求（`/smart/edu/`）反向代理到 FastAPI
- **缓存策略**：JS/CSS/图片缓存 1 天（`public, max-age=86400`）；HTML 不缓存（`no-cache`）；缓存类型由 `map $uri $static_cache_control` 决定
- **负载均衡**：`ip_hash` 将同一客户端 IP 路由到固定节点，保证 `InMemorySaver` 中的对话上下文连续
- **流式响应**：proxy location 内 `proxy_buffering off`，token 实时透传；超时读写均 120s
- **Gzip**：开启，阈值 1KB，压缩 JS/CSS/JSON 等文本类型

```bash
nginx -t        # 验证配置
nginx -s reload # 热重载（不中断现有连接）
```

### 会话机制

- Session 加密存储在客户端 Cookie（Starlette `SessionMiddleware`，HMAC 签名，TTL 3600s）
- `session_id` 为 UUID，首次请求时生成，作为 LangGraph `thread_id` 实现多轮记忆
- Nginx `ip_hash` 保证同一用户的请求始终路由到同一节点（InMemorySaver 进程内存隔离）
- `POST /new-chat` 清除 session，下次请求自动生成新 `session_id`

## 数据库 Schema（Neo4j 节点类型）

完整节点类型：`Course`, `Chapter`, `Question`, `Knowledge`, `Category`, `Paper`, `Subject`, `Video`, `Teacher`, `Student`, `Price`

**注意事项**：
- `Teacher`、`Student`、`Price` 不在 `NODE_LIST`，实体对齐时被显式过滤跳过
- `Knowledge` 节点无 `id` 字段，向量索引以 `name` 作为唯一标识
- 新增节点类型需同步更新：`NODE_LIST`、`sync_cli.py` 同步逻辑、Neo4j 向量/全文索引
- `SyncTextHandler`（UIE 抽取知识点）需要 **GPU** 环境（`device="gpu"`）
- `uie_pytorch/` 目录由 `sync_cli.py` 在运行时动态加入 `sys.path`
