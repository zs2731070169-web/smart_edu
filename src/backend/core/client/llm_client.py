import logging
from typing import Any

import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from backend.config.settings import EMBEDDINGS_MODEL, LLM_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("llm_client")

# 向量模型(本地)
embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDINGS_MODEL,
    encode_kwargs={"normalize_embeddings": True},
    model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"}
)
logger.info("embedding 模型加载完成")


def _build_chat(kwargs: dict[str, Any]) -> ChatOpenAI:
    """统一从 LLM_CONFIG 构建 ChatOpenAI,只切 model 名

    disable_thinking=True:dashscope 部分模型默认开启「思考模式」,与
    `with_structured_output(method="function_calling")` 强制设置的
    tool_choice=required 冲突。需要结构化输出的模型必须关闭思考模式。
    """
    extra_body = {"enable_thinking": False} if kwargs['disable_thinking'] else None
    return ChatOpenAI(
        model=kwargs['model'],
        base_url=LLM_CONFIG["url"],
        api_key=LLM_CONFIG["api_key"],
        temperature=kwargs['temperature'],
        extra_body=extra_body,
    )


# 按任务职责绑定模型(便于后续单点替换)
# - 意图识别 + 最终回答:deepseek-v3.2(对话/语义理解);意图识别需结构化输出,关思考模式
llm_chat = _build_chat({
    "model": "deepseek-v3.2",
    "disable_thinking": True,
    "temperature": 0.3
})
logger.info("[llm_chat] deepseek-v3.2 加载完成 - 用于 intent / answer")

# - 实体抽取:qwen-max(中文实体识别);需结构化输出,关思考模式
llm_extract = _build_chat({
    "model": "qwen-max",
    "disable_thinking": True,
    "temperature": 0
})
logger.info("[llm_extract] qwen-max 加载完成 - 用于 extract_entities")

# - Cypher 生成 + 校验:glm-5.1;校验需结构化输出,关思考模式
llm_cypher = _build_chat({
    "model": "glm-5.1",
    "disable_thinking": True,
    "temperature": 0
})
logger.info("[llm_cypher] glm-5.1 加载完成 - 用于 generate_cypher / validate_cypher")
