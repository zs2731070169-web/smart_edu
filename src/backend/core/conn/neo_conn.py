import logging

from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from backend.config.settings import NEO4J_CONFIG, EMBEDDINGS_MODEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("neo_conn")


class Neo4jWriter:

    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(NEO4J_CONFIG["uri"], auth=NEO4J_CONFIG.get("auth"))
            self.driver.verify_connectivity()
            logger.info("Neo4j 数据库连接初始化成功")
        except AuthError:
            logger.error("Neo4j 认证失败，请检查用户名/密码")
            raise
        except ServiceUnavailable:
            logger.error("Neo4j 服务不可达，请检查地址/端口/服务状态")
            raise
        except Exception as e:
            logger.error(f"Neo4j 驱动初始化失败: {str(e)}", exc_info=True)
            raise

        self.embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDINGS_MODEL,
            encode_kwargs={"normalize_embeddings": True}
        )
        logger.info("embedding模型加载完成")

        self.embedding_dim = len(self.embedding_model.embed_query("embedding"))

    def __enter__(self):
        return self  # 返回 self,即返回客户端实例

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.close()
