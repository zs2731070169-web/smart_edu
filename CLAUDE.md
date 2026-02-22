# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

AI 驱动的智能教育系统，基于 **RAG + 知识图谱**架构，提供自然语言智能问答服务。用户通过 Web 界面提问，后端 Agent 自动完成实体抽取→实体对齐→Cypher 生成→图查询→流式回答的完整链路。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务（在项目根目录下执行）
cd src && python -m backend.app
# 服务监听：http://localhost:8000/smart/edu/

# 数据同步：MySQL → Neo4j（首次部署或数据变更后执行）
cd src && python -m sync_data.sync_handler

# UIE 模型微调
cd uie_pytorch && python finetune.py

# UIE 模型评估
cd uie_pytorch && python evaluate.py

# Doccano 标注数据转换
cd uie_pytorch && python doccano.py
```

## 核心架构

### 请求处理流程

```
Web UI → POST /smart/edu/chat
  → ChatService.retrieval_chat_stream()  (src/backend/service.py)
  → Agent.astream_events()              (src/agent/__init__.py)
  → 流式返回 token
```

### Agent 工作链（LangGraph）

`src/agent/__init__.py` 中的 `gen_agent()` 构建 LangGraph ReAct Agent，执行以下步骤：

1. **意图判断**：对话型直接回答，知识查询继续后续步骤
2. **实体抽取** (`extract_entities`)：LLM 从问题中识别实体和标签（基于 `NODE_LIST`）
3. **实体对齐** (`entities_align_async`)：混合检索（向量 + 全文）将用户实体对齐到图数据库中的节点
4. **Cypher 生成**：LLM 根据图 schema 和对齐实体生成 Cypher 查询
5. **Cypher 校验** (`validate_cypher`)：语法+语义双重校验，失败则纠错重试
6. **图查询** (`query_cypher`)：执行 Cypher，返回 JSON 结果
7. **自然语言回答**：整合结果，流式输出给用户

### 混合检索原理

`src/agent/retrieval_tools.py` 中的 `_search_entity()`：
```
score = vector_score * alpha + fulltext_score * (1 - alpha)
# alpha 默认 0.5，threshold 默认 0.5
```

- 向量索引命名规范：`{label_lower}_vector_index`
- 全文索引命名规范：`{label_lower}_fulltext_index`（CJK 分析器）

### 模块职责

| 路径 | 职责 |
|------|------|
| `src/backend/app.py` | FastAPI 入口，SessionMiddleware，路由定义 |
| `src/backend/service.py` | 流式聊天服务，过滤 Agent 中间节点输出 |
| `src/agent/__init__.py` | LangGraph Agent 构建，`gen_agent()` 懒加载 |
| `src/agent/context.py` | 全局单例：LLM、Neo4j driver、embedding 模型、线程池 |
| `src/agent/retrieval_tools.py` | 4 个 LangChain 工具：实体抽取、对齐、Cypher 校验、图查询 |
| `src/agent/prompts.py` | Agent 系统提示词，含完整 schema 和约束规则 |
| `src/config/config.py` | 所有配置项（数据库、LLM、模型路径、节点类型） |
| `src/sync_data/` | MySQL → Neo4j 数据同步，全文/向量索引创建 |
| `uie_pytorch/` | UIE 通用信息抽取模型（实体/关系抽取），支持 ONNX 和 PyTorch 后端 |

## 配置说明

所有配置集中在 `src/config/config.py`，支持通过 `.env` 文件覆盖（参考 `.env.example`）：

- **LLM**：使用 OpenAI 兼容接口代理，默认模型 `gpt-5.2`（实体抽取/Agent）和 `claude-opus-4-6`（Cypher 校验）
- **Neo4j**：`neo4j://localhost:7687`，图数据库存储知识图谱
- **MySQL**：`localhost:3306`，存储原始教育结构化数据
- **嵌入模型**：`models/bge-base-zh-v1.5`（本地 HuggingFace 模型）
- **UIE 模型**：`models/uie_base_pytorch`，微调检查点在 `checkpoint/`
- **AGENT_WITH_MEMORY**：控制 Agent 是否启用跨轮对话记忆（InMemorySaver）
- **NODE_LIST**：`['Course', 'Chapter', 'Question', 'Knowledge', 'Category', 'Paper', 'Subject', 'Video']`

## 部署

- **服务管理**：`deploy/smart_edu.service`（Systemd），工作目录为 `/home/smart_edu/app/src`
- **反向代理**：`deploy/nginx.conf`，监听 443，关闭 `proxy_buffering`（流式响应必须）
- **会话**：基于加密 Cookie，TTL 3600s，`/new-chat` 接口清除历史

## 数据库 Schema（Neo4j 节点类型）

`Course`, `Chapter`, `Question`, `Knowledge`, `Category`, `Paper`, `Subject`, `Video`, `Teacher`, `Student`

新增节点类型时需同步更新：`config.py` 的 `NODE_LIST`、`sync_data/sync_handler.py` 中的同步逻辑、以及 Neo4j 向量/全文索引。