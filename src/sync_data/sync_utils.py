# 配置日志，便于排查问题
import logging
from typing import List

import pymysql
from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable, Neo4jError
from pymysql.cursors import DictCursor

from config.config import MYSQL_CONFIG, NEO4J_CONFIG, EMBEDDINGS_MODEL
from sync_data.schema import NodeRelation, Node, FullIndex, VectorIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SyncUtils")


class MysqlReader:

    def __init__(self, config=None):
        self.config = MYSQL_CONFIG or config

    def __enter__(self):
        """进入上下文时自动建立连接"""
        try:
            self.conn = pymysql.connect(**self.config)
            self.cursor = self.conn.cursor(cursor=DictCursor)  # 使用字典游标DictCursor，将数据库查询结果以 Python 字典的形式返回
            logger.info("MySQL 数据库连接建立成功")
            return self
        except pymysql.Error as e:
            raise Exception(f"数据库连接失败：{str(e)}") from e  # 抛出原始异常e的对象、堆栈、类型，而不仅是异常描述

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def read_all(self, sql):
        self.cursor.execute(sql)
        return self.cursor.fetchall()  # 返回所有数据


class Neo4jWriter:

    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(**NEO4J_CONFIG)
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

    def create_node(self, node: Node):
        keys = list(node.properties[0].keys())
        # 动态生成Cypher语句
        cypher = f"""
            UNWIND $raws AS raw
            MERGE (:{node.label} {{{", ".join([f"{key}: raw.{key}" for key in keys])}}})
        """
        self.execute_cypher(self.driver, cypher, {"raws": node.properties}, err_msg="节点创建失败")
        logger.info(f"节点[{node.label}]创建完毕")

    def create_relation(self, node_relation: NodeRelation):
        cypher = f"""
        UNWIND $raws AS raw
        MATCH (start:{node_relation.start_label} {{id:raw.start_id}}), (end:{node_relation.end_label} {{id:raw.end_id}})
        MERGE (start)-[r:{node_relation.relation_label}]->(end)
        SET r += raw.relation_prop
        """
        self.execute_cypher(self.driver, cypher, {"raws": node_relation.properties}, err_msg="节点创建失败")
        logger.info(
            f"关系[{node_relation.start_label}-{node_relation.relation_label}-{node_relation.end_label}]创建完毕")

    def create_full_index(self, full_index_list: List[FullIndex]):
        """
        创建全文索引
        :param full_index_list:
        :return:
        """
        # 创建全文索引
        for full_index in full_index_list:
            cypher = f"""
            CREATE FULLTEXT INDEX {full_index.index_name} IF NOT EXISTS
            FOR (n:{full_index.label}) ON EACH [n.{full_index.property}]
            """
            self.execute_cypher(self.driver, cypher, err_msg="全文索引创建失败")

            logger.info(f"全文索引[{full_index.index_name}]创建完毕")

    def create_vector_index(self, vector_index_list: List[VectorIndex]):
        """
        创建向量索引
        :param vector_index_list:
        :return:
        """

        for vector_index in vector_index_list:
            label = vector_index.label
            index_name = vector_index.index_name
            text_property = vector_index.text_property
            id_property = vector_index.id_property

            # 查询所有的id和name
            cypher = f"""
            MATCH(n:{label}) 
            WHERE n.embedding IS NULL
            RETURN n.{id_property} AS id, n.{text_property} AS text
            """
            records = self.driver.execute_query(cypher).records

            # 生成id-text对列表
            id_text_list = [(record.get('id'), record.get('text')) for record in records]

            if not id_text_list:
                continue

            ids, texts = zip(*id_text_list)
            ids = list(ids)
            texts = list(texts)

            # 进行词嵌入
            embed_docs = self.embedding_model.embed_documents(texts)

            # 构建id，嵌入向量对
            rows = [{"id": id, "embedding": embed_doc} for id, embed_doc in zip(ids, embed_docs)]

            # 创建embedding属性
            cypher = f"""
            UNWIND $rows AS row
            MATCH (n:{label} {{{id_property}: row.id}})
            SET n.embedding = row.embedding
            """
            self.execute_cypher(self.driver, cypher, parameters={"rows": rows}, err_msg="向量索引创建失败")

            # 创建向量索引
            cypher = f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS 
            FOR (m:{label})
            ON m.embedding
            OPTIONS {{ indexConfig: {{
                    `vector.dimensions`: {self.embedding_dim},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
            """
            self.execute_cypher(self.driver, cypher, err_msg="向量索引创建失败")

            logger.info(f"向量索引[{index_name}]创建完毕")

    def drop_index(self, cypher):
        """
        删除索引
        :return:
        """
        # 删除索引
        records = self.driver.execute_query(cypher).records
        if records:
            for record in records:
                self.execute_cypher(self.driver, f"DROP INDEX {record['name']} IF EXISTS")
            logging.info(f"索引删除完毕")

    def execute_cypher(self, driver, cypher, parameters=None, err_msg=""):
        try:
            if parameters:
                driver.execute_query(cypher, parameters_=parameters)
            else:
                driver.execute_query(cypher)
        except Neo4jError as e:
            logger.error(f"{err_msg}：{e.message}")
            raise
