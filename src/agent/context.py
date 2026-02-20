import logging
from concurrent.futures import ThreadPoolExecutor

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI
from neo4j import GraphDatabase

from config.config import NEWCOIN_CONFIG, NEO4J_CONFIG, EMBEDDINGS_MODEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Agent")

# 加载neo4j驱动
driver = GraphDatabase.driver(**NEO4J_CONFIG)
logger.info("Neo4j 驱动初始化成功")

# 加载neo4j图
graph = Neo4jGraph(
    url=NEO4J_CONFIG["uri"],
    username=NEO4J_CONFIG["auth"][0],
    password=NEO4J_CONFIG["auth"][1]
)
logger.info("Neo4j 图加载完成")

# 加载向量模型
embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDINGS_MODEL,
    encode_kwargs={"normalize_embeddings": True}
)
logger.info("embedding 模型加载完成")

# 加载实体抽取模型
llm_gpt = ChatOpenAI(
    model="gpt-5.2",
    base_url=NEWCOIN_CONFIG["url"],
    api_key=NEWCOIN_CONFIG["api_key"],
    temperature=NEWCOIN_CONFIG["temperature"],
)
logger.info("gpt-5.2 模型加载完成")

# 加载tex2sql模型
llm_opus = ChatOpenAI(
    model="claude-opus-4-6",
    base_url=NEWCOIN_CONFIG["url"],
    api_key=NEWCOIN_CONFIG["api_key"]
)
logger.info("claude-opus-4-6 模型加载完成")

# 执行混合检索的线程池
thread_pool_executor = ThreadPoolExecutor(max_workers=10)
logger.info("线程池初始化完毕...")
