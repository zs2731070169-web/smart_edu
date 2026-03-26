import logging

import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from backend.config.settings import EMBEDDINGS_MODEL, CLOSEAI_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("llm_client")

# 加载向量模型
embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDINGS_MODEL,
    encode_kwargs={"normalize_embeddings": True},
    model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"}
)
logger.info("embedding 模型加载完成")

# 加载实体抽取、智能体、校验cypher模型
# llm_deepseek = ChatOpenAI(
#     model="deepseek-chat",
#     base_url=CLOSEAI_CONFIG["url"],
#     api_key=CLOSEAI_CONFIG["api_key"],
#     temperature=CLOSEAI_CONFIG["temperature"],
# )
# logger.info("deepseek-chat 模型加载完成")

# llm_opus = ChatOpenAI(
#     model="claude-opus-4-6",
#     base_url=NEWCOIN_CONFIG["url"],
#     api_key=NEWCOIN_CONFIG["api_key"]
# )
# logger.info("claude-opus-4-6 模型加载完成")

# 加载实体抽取、智能体、校验cypher模型
llm_gpt = ChatOpenAI(
    model="gpt-5.2",
    base_url=CLOSEAI_CONFIG["url"],
    api_key=CLOSEAI_CONFIG["api_key"],
    temperature=CLOSEAI_CONFIG["temperature"],
)
logger.info("gpt-5.2 模型加载完成")

# 加载tex2sql模型
llm_opus = ChatOpenAI(
    model="claude-opus-4-6",
    base_url=CLOSEAI_CONFIG["url"],
    api_key=CLOSEAI_CONFIG["api_key"],
    temperature=CLOSEAI_CONFIG["temperature"],
)

logger.info("claude-opus-4-6 模型加载完成")
