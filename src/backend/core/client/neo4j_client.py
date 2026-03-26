import logging
from neo4j import GraphDatabase
from langchain_neo4j import Neo4jGraph

from backend.config.settings import NEO4J_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("neo4j_client")

_auth = NEO4J_CONFIG.get("auth")

# 加载neo4j图（无密码时 username/password 传空字符串）
graph = Neo4jGraph(
    url=NEO4J_CONFIG["uri"],
    username=_auth[0] if _auth else "",
    password=_auth[1] if _auth else ""
)
logger.info("Neo4j 图加载完成")

# 加载neo4j驱动（无密码时 auth=None）
driver = GraphDatabase.driver(NEO4J_CONFIG["uri"], auth=_auth)
logger.info("Neo4j 驱动初始化成功")

# 获取图结构
graph_schema = graph.schema
logger.info("获取图结构完毕")
