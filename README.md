# Smart Edu

AI 驱动的智能教育系统后端，基于 **RAG + 知识图谱**架构，提供自然语言智能问答服务。

## 特性 Features

- 基于 RAG（检索增强生成）与知识图谱
- 支持复杂实体抽取、实体对齐、自动 Cypher 生成与校验
- 流式问答，精准业务知识查询
- 支持全量数据同步，从 MySQL 到 Neo4j
- 支持 UIE 模型微调、评估及数据标注

## 目录结构

```
src/
  backend/
    core/       # Agent、LLM、检索、图谱等核心功能
    service/    # 聊天及其他后端服务
    web/        # FastAPI 接口与启动入口
    prompts/    # 提示词与系统约束
    ingestion/  # 数据同步和数据管道
front/          # 前端静态资源（如有）
uie_pytorch/    # UIE 微调与评估脚本
```

## 快速开始

1. 克隆本仓库

   ```bash
   git clone https://github.com/zs2731070169-web/smart_edu.git
   cd smart_edu
   ```

2. 安装依赖

   ```bash
   pip install -r requirements.txt
   ```

3. 启动服务

   ```bash
   # 在项目根目录
   cd src && python -m backend.web.api.app
   # 或指定端口
   APP_PORT=8001 cd src && python -m backend.web.api.app
   ```

4. 数据同步（可选，用于初始化 Neo4j）

   ```bash
   cd src && python -m backend.ingestion.cli.sync_cli
   ```

5. 测试 Agent

   ```bash
   cd src && python -m backend.core.agent
   ```

## 开发&贡献

欢迎提交 issue 与 PR，协作开发请先阅读[贡献指南](CONTRIBUTING.md)（如有）。

## 许可证 License

本项目采用 MIT License - 详见 [LICENSE](LICENSE)
