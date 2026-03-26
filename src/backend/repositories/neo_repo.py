import logging
from typing import List

from neo4j.exceptions import Neo4jError

from backend.core.client.llm_client import embedding_model
from backend.core.client.neo4j_client import driver
from backend.core.db.neo_conn import Neo4jWriter
from backend.sync.schema.schema import Node, NodeRelation, VectorIndex, FullIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("neo4j_repo")


class Neo4jRepo:

    def __init__(self):
        # Neo4jWriter 仅用于获取 embedding_dim（向量维度）
        self.neo4j_writer = Neo4jWriter()

    def create_node(self, node: Node):
        keys = list(node.properties[0].keys())
        cypher = f"""
            UNWIND $raws AS raw
            MERGE (:{node.label} {{{", ".join([f"{key}: raw.{key}" for key in keys])}}})
        """
        self.execute_cypher(cypher, {"raws": node.properties}, err_msg="节点创建失败")
        logger.info(f"节点[{node.label}]创建完毕")

    def create_relation(self, node_relation: NodeRelation):
        cypher = f"""
        UNWIND $raws AS raw
        MATCH (start:{node_relation.start_label} {{id:raw.start_id}}), (end:{node_relation.end_label} {{id:raw.end_id}})
        MERGE (start)-[r:{node_relation.relation_label}]->(end)
        SET r += raw.relation_prop
        """
        self.execute_cypher(cypher, {"raws": node_relation.properties}, err_msg="关系创建失败")
        logger.info(
            f"关系[{node_relation.start_label}-{node_relation.relation_label}-{node_relation.end_label}]创建完毕")

    def create_vector_index(self, vector_index_list: List[VectorIndex]):
        """创建向量索引"""
        for vector_index in vector_index_list:
            label = vector_index.label
            index_name = vector_index.index_name
            text_property = vector_index.text_property
            id_property = vector_index.id_property

            # 查询所有尚未生成 embedding 的节点
            cypher = f"""
            MATCH(n:{label})
            WHERE n.embedding IS NULL
            RETURN n.{id_property} AS id, n.{text_property} AS text
            """
            records = driver.execute_query(cypher).records

            id_text_list = [(record.get('id'), record.get('text')) for record in records]
            if not id_text_list:
                continue

            ids, texts = zip(*id_text_list)
            embed_docs = embedding_model.embed_documents(list(texts))
            rows = [{"id": id, "embedding": embed_doc} for id, embed_doc in zip(ids, embed_docs)]

            # 写入 embedding 属性
            cypher = f"""
            UNWIND $rows AS row
            MATCH (n:{label} {{{id_property}: row.id}})
            SET n.embedding = row.embedding
            """
            self.execute_cypher(cypher, parameters={"rows": rows}, err_msg="向量属性写入失败")

            # 创建向量索引
            cypher = f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (m:{label})
            ON m.embedding
            OPTIONS {{ indexConfig: {{
                    `vector.dimensions`: {self.neo4j_writer.embedding_dim},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
            """
            self.execute_cypher(cypher, err_msg="向量索引创建失败")
            logger.info(f"向量索引[{index_name}]创建完毕")

    def drop_index(self, cypher):
        """删除索引"""
        records = driver.execute_query(cypher).records
        if records:
            for record in records:
                self.execute_cypher(f"DROP INDEX {record['name']} IF EXISTS")
            logger.info("索引删除完毕")

    def execute_cypher(self, cypher, parameters=None, err_msg=""):
        try:
            if parameters:
                driver.execute_query(cypher, parameters_=parameters)
            else:
                driver.execute_query(cypher)
        except Neo4jError as e:
            logger.error(f"{err_msg}：{e.message}")
            raise

    def create_full_index(self, full_index_list: List[FullIndex]):
        """创建全文索引"""
        for full_index in full_index_list:
            cypher = f"""
             CREATE FULLTEXT INDEX {full_index.index_name} IF NOT EXISTS
             FOR (n:{full_index.label}) ON EACH [n.{full_index.property}]
             OPTIONS {{
                 indexConfig: {{
                   `fulltext.analyzer`: 'cjk'
                 }}
             }}
             """
            self.execute_cypher(cypher, err_msg="全文索引创建失败")
            logger.info(f"全文索引[{full_index.index_name}]创建完毕")


# 单例，供 sync_cli 直接调用
neo4j_repo = Neo4jRepo()
