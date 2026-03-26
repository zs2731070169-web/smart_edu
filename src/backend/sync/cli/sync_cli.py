import html
import logging
import os
import re
import sys

from backend.repositories.mysql_repo import mysql_repo
from backend.repositories.neo_repo import neo4j_repo
from backend.sync.schema.schema import Node, NodeRelation, VectorIndex, FullIndex

sys.path.append(os.path.join(os.path.dirname(__file__), "../../uie_pytorch"))

from backend.config.settings import CHECKPOINT_DIR, BASE_MODEL
from uie_pytorch.uie_predictor import UIEPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sync_cli")


def _standardize_text(text: str) -> str:
    """
    清理数据
    :param driver:
    :param text:
    :return:
    """
    if not isinstance(text, str):
        return text

    # 解码html（如 &lt; -> <, &gt; -> >, &amp; -> & 等）
    text = html.unescape(text)

    # 移除html, 匹配以 < 开头、以 > 结尾，中间不包含 > 的任意内容，去掉&nbsp;&lt;p&gt;&lt;strong&gt;字符，也就是匹配一个完整的 HTML 标签
    text = re.sub(r"<[^>]+>", "", text).strip()

    # 全角转半角
    for char in text:
        # 获取字符 char 对应的 Unicode 编码
        uchar = ord(char)
        # 全角转半角
        if uchar >= 65281 and uchar <= 65374:
            text = text.replace(char, chr(uchar - 65248))
        elif uchar == 12288:
            text = text.replace(char, chr(32))

    # 去除首尾空格，将内部一个或多个连续的空白字符转为一个空格,"a b\t\n c" 会被处理为 "a b c"
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    # 转为小写
    text = text.lower()
    return text


class SyncMysqlHandler:

    def sync_nodes(self, reader, writer):
        # 同步分类节点
        records = reader.read_all("SELECT id, category_name FROM base_category_info")
        properties = [{"id": record["id"], "name": record["category_name"]} for record in records]
        writer.create_node(Node(label="Category", properties=properties))

        # 同步学科节点
        records = reader.read_all("SELECT id, subject_name FROM base_subject_info")
        properties = [{"id": record["id"], "name": record["subject_name"]} for record in records]
        writer.create_node(Node(label="Subject", properties=properties))

        # 同步课程节点
        records = reader.read_all("SELECT id, course_name FROM course_info")
        properties = [{"id": record["id"], "name": record["course_name"]} for record in records]
        writer.create_node(Node(label="Course", properties=properties))

        # 同步教师节点
        records = reader.read_all("SELECT DISTINCT teacher FROM course_info")
        properties = [{"teacher_name": record["teacher"]} for record in records]
        writer.create_node(Node(label="Teacher", properties=properties))

        # # 同步价格节点
        records = reader.read_all("SELECT actual_price FROM course_info")
        properties = [
            {
                "price": str(record["actual_price"]) if record["actual_price"] else "0"
            }
            for record in records
        ]
        writer.create_node(Node(label="Price", properties=properties))

        # # 同步章节
        records = reader.read_all("SELECT id, chapter_name FROM chapter_info")
        properties = [{"id": record["id"], "name": record["chapter_name"]} for record in records]
        writer.create_node(Node(label="Chapter", properties=properties))

        # 同步视频
        records = reader.read_all("SELECT id, video_name FROM video_info")
        properties = [{"id": record["id"], "name": record["video_name"]} for record in records]
        writer.create_node(Node(label="Video", properties=properties))

        # 同步试卷
        records = reader.read_all("SELECT id, paper_title FROM test_paper")
        properties = [{"id": record["id"], "name": _standardize_text(record["paper_title"])} for record in records]
        writer.create_node(Node(label="Paper", properties=properties))

        # 同步试题
        records = reader.read_all("SELECT id, question_txt FROM test_question_info")
        properties = [{"id": record["id"], "name": _standardize_text(record["question_txt"])} for record in records]
        writer.create_node(Node(label="Question", properties=properties))

        # 同步学生
        records = reader.read_all("SELECT id, birthday, gender FROM user_info")
        properties = [{"id": record["id"], "birthday": record["birthday"],
                       "gender": record["gender"] if record["gender"] else ""} for record in records]
        writer.create_node(Node(label="Student", properties=properties))

    def sync_relations(self, reader, writer):
        # 建立课程-学科关系
        records = reader.read_all("SELECT id, subject_id FROM course_info")
        properties = [{"start_id": record["id"], "end_id": record["subject_id"], "relation_prop": {}} for record in
                      records]
        node_relation = NodeRelation(start_label="Course", end_label="Subject", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立学科-分类关系
        records = reader.read_all("SELECT id, category_id FROM base_subject_info")
        properties = [{"start_id": record["id"], "end_id": record["category_id"], "relation_prop": {}} for record in
                      records]
        node_relation = NodeRelation(start_label="Subject", end_label="Category", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立视频-章节关系
        records = reader.read_all("SELECT id, chapter_id FROM video_info")
        properties = [{"start_id": record["id"], "end_id": record["chapter_id"], "relation_prop": {}} for record in
                      records]
        node_relation = NodeRelation(start_label="Video", end_label="Chapter", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立章节-课程关系
        records = reader.read_all("SELECT id, course_id FROM chapter_info")
        properties = [{"start_id": record["id"], "end_id": record["course_id"], "relation_prop": {}} for record in
                      records]
        node_relation = NodeRelation(start_label="Chapter", end_label="Course", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立试题-试卷关系
        records = reader.read_all("SELECT question_id, paper_id FROM test_paper_question")
        properties = [{"start_id": record["question_id"], "end_id": record["paper_id"], "relation_prop": {}} for record
                      in records]
        node_relation = NodeRelation(start_label="Question", end_label="Paper", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立试卷-课程关系
        records = reader.read_all("SELECT id, course_id FROM test_paper")
        properties = [{"start_id": record["id"], "end_id": record["course_id"], "relation_prop": {}} for record in
                      records]
        node_relation = NodeRelation(start_label="Paper", end_label="Course", relation_label="BELONG",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 建立课程-教师关系
        records = reader.read_all("SELECT id, teacher FROM course_info")
        properties = [{"course_id": record["id"], "teacher_name": record["teacher"], "relation_prop": {}} for record in
                      records]
        cypher = f"""
        UNWIND $raws AS raw
        MATCH (start:Course {{id:raw.course_id}}), (end:Teacher {{teacher_name:raw.teacher_name}})
        MERGE (start)-[:HAVE]->(end)
        """
        writer.execute_cypher(cypher, parameters={"raws": properties},
                              err_msg="课程-教师关系创建失败")

        # 建立课程-价格关系
        records = reader.read_all("SELECT id, actual_price FROM course_info")
        properties = [
            {
                "course_id": record["id"],
                "price": str(record["actual_price"]) if record["actual_price"] else "0"
            } for record in records]
        cypher = f"""
                UNWIND $raws AS raw
                MATCH (start:Course {{id:raw.course_id}}), (end:Price {{price:raw.price}})
                MERGE (start)-[:HAVE]->(end)
                """
        writer.execute_cypher(cypher, parameters={"raws": properties},
                              err_msg="课程-价格关系创建失败")

        # 学生-课程关系
        records = reader.read_all("SELECT user_id, course_id, create_time FROM favor_info")
        properties = [
            {"start_id": record["user_id"], "end_id": record["course_id"],
             "relation_prop": {"create_time": record["create_time"]}} for
            record in records]
        node_relation = NodeRelation(start_label="Student", end_label="Course", relation_label="FAVOR",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 学生-试题关系
        records = reader.read_all("SELECT user_id, question_id, is_correct FROM test_exam_question")
        properties = [
            {
                "start_id": record["user_id"],
                "end_id": record["question_id"],
                "relation_prop": {"is_correct": record["is_correct"]}
            } for record in records]
        node_relation = NodeRelation(start_label="Student", end_label="Question", relation_label="ANSWER",
                                     properties=properties)
        writer.create_relation(node_relation)

        # 学生-章节视频关系
        records = reader.read_all(
            "SELECT user_id, chapter_id, position_sec, create_time, update_time FROM user_chapter_progress")
        properties = [
            {
                "start_id": record["user_id"],
                "end_id": record["chapter_id"],
                "relation_prop": {
                    "position_sec": record["position_sec"],
                    "last_view_time": record["update_time"] if record["update_time"] else record["create_time"]
                }
            }
            for record in records
        ]
        node_relation = NodeRelation(start_label="Student", end_label="Chapter", relation_label="WATCH",
                                     properties=properties)
        writer.create_relation(node_relation)


class SyncTextHandler:

    def __init__(self):
        self.ie = UIEPredictor(model=BASE_MODEL, task_path=CHECKPOINT_DIR / "model_best", schema=["knowledge"],
                               device="gpu")

    def sync_knowledge_node_and_relation(self, reader, writer):
        """
        同步知识点,章节名称、课程概述、试题描述
        :param reader:
        :param writer:
        :return:
        """

        # 获取课程文本、试题文本、章节文本
        texts = reader.read_all("SELECT id, course_introduce AS text FROM course_info")
        _standardize_text(texts)
        self.execute_sync(writer, texts, "Course")

        texts = reader.read_all("SELECT id, chapter_name AS text FROM chapter_info")
        _standardize_text(texts)
        self.execute_sync(writer, texts, "Chapter")

        texts = reader.read_all("SELECT id, question_txt AS text FROM test_question_info")
        _standardize_text(texts)
        self.execute_sync(writer, texts, "Question")

    def execute_sync(self, writer, texts, start_label):
        # 无更多数据则退出
        if not texts:
            return

        # 获取批量的id和text
        texts = [{"id": record["id"], "text": record["text"]} for record in texts]

        batch_size = 6
        properties = []
        relation_properties = []

        for text_index in range(0, len(texts), batch_size):
            # 获取批量的文本
            batch_text = texts[text_index: text_index + batch_size]
            for text in batch_text:
                # 预测知识点
                predict_knowledge = self.ie(text["text"])
                # 提取并去重知识点
                unique_knowledge = {
                    text["text"] for item in predict_knowledge for text in item.get("knowledge", [])
                }
                # 收集知识点属性
                properties.extend([{"name": item} for item in unique_knowledge])
                # 收集课程-知识点、章节-知识点、试题-知识点关系
                relation_properties.extend({"id": text["id"], "name": item} for item in unique_knowledge)

        # 创建知识点节点
        if properties:
            writer.create_node(Node(label="Knowledge", properties=properties))

        # 建立课程-知识点关系
        if relation_properties:
            cypher = f"""
               UNWIND $raws AS raw
               MATCH (start:{start_label} {{id:raw.id}}), (end:Knowledge {{name:raw.name}})
               MERGE (start)-[:HAVE]->(end)
               """
            writer.execute_cypher(cypher, parameters={"raws": relation_properties},
                                  err_msg="课程-知识点关系创建失败")
            logger.info(f"创建[{start_label}-HAVE-Knowledge]关系完成")

    def sync_knowledge_relations(self, writer):
        """
        同步知识点关系
        :param reader:
        :param writer:
        :return:
        """
        # 创建知识点先修关系
        cypher = """
        MATCH (knowledge:Knowledge)<-[:HAVE]-(chapter:Chapter)-[:BELONG]->(course:Course)<-[:BELONG]-(pre_chapter:Chapter)-[:HAVE]->(pre_knowledge:Knowledge)
        WHERE chapter.id > pre_chapter.id AND knowledge <> knowledge
        WITH DISTINCT knowledge, pre_knowledge
        MERGE (knowledge)-[:NEED]->(pre_knowledge)
       """
        writer.execute_cypher(cypher, err_msg="知识点先修关系创建失败")
        logger.info("创建知识点先修关系完成")

        # 创建知识点包含关系
        cypher = """
        MATCH (knowledge:Knowledge)<-[:HAVE]-(chapter:Chapter)-[:BELONG]->(course:Course)-[:HAVE]->(bigger_knowledge:Knowledge)
        WHERE knowledge <> bigger_knowledge
        WITH DISTINCT knowledge, bigger_knowledge
        MERGE (knowledge)-[:BELONG]->(bigger_knowledge)
        """
        writer.execute_cypher(cypher, err_msg="知识点包含关系创建失败")
        logger.info("创建知识点包含关系完成")

        # 创建知识点相关关系
        cypher = """
        MATCH (knowledge:Knowledge)<-[:HAVE]-(chapter:Chapter)-[:BELONG]->(course:Course)-[:HAVE]->(related_knowledge:Knowledge)
        WHERE knowledge <> related_knowledge AND elementId(knowledge) < elementId(related_knowledge)
        WITH DISTINCT knowledge, related_knowledge
        MERGE (knowledge)-[:RELATED]->(related_knowledge)
        """
        writer.execute_cypher(cypher, err_msg="知识点相关关系创建失败")
        logger.info("创建知识点相关关系完成")


class SyncIndexHandler:
    """
    同步索引处理器
    :return:
    """

    def sync_fulltext_index(self, writer):
        # 删除全文索引
        writer.drop_index("SHOW FULLTEXT INDEX")

        fulltext_list = [
            FullIndex(label="Course", index_name="course_fulltext_index", property="name"),
            FullIndex(label="Chapter", index_name="chapter_fulltext_index", property="name"),
            FullIndex(label="Question", index_name="question_fulltext_index", property="name"),
            FullIndex(label="Knowledge", index_name="knowledge_fulltext_index", property="name"),
            FullIndex(label="Category", index_name="category_fulltext_index", property="name"),
            FullIndex(label="Paper", index_name="paper_fulltext_index", property="name"),
            FullIndex(label="Subject", index_name="subject_fulltext_index", property="name"),
            FullIndex(label="Video", index_name="video_fulltext_index", property="name")
        ]
        writer.create_full_index(fulltext_list)

    def sync_vector_index(self, writer):
        writer.drop_index("SHOW VECTOR INDEX")

        # 删除embedding属性
        cypher = f"""
        MATCH (n)
        REMOVE n.embedding
        """
        writer.execute_cypher(cypher, err_msg="向量属性删除失败")
        logger.info("embedding属性删除完毕")

        vector_list = [
            VectorIndex(label="Course", index_name="course_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Chapter", index_name="chapter_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Question", index_name="question_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Knowledge", index_name="knowledge_vector_index", id_property="name",
                        text_property="name"),
            VectorIndex(label="Category", index_name="category_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Paper", index_name="paper_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Subject", index_name="subject_vector_index", id_property="id", text_property="name"),
            VectorIndex(label="Video", index_name="video_vector_index", id_property="id", text_property="name")
        ]
        writer.create_vector_index(vector_list)


if __name__ == '__main__':
    sync_mysql_handler = SyncMysqlHandler()
    sync_text_handler = SyncTextHandler()
    sync_index_handler = SyncIndexHandler()


    # 同步结构化数据节点
    sync_mysql_handler.sync_nodes(mysql_repo, neo4j_repo)
    sync_mysql_handler.sync_relations(mysql_repo, neo4j_repo)
    # 同步文本数据节点
    sync_text_handler.sync_knowledge_node_and_relation(mysql_repo, neo4j_repo)
    sync_text_handler.sync_knowledge_relations(neo4j_repo)
    # 同步索引
    sync_index_handler.sync_fulltext_index(neo4j_repo)
    sync_index_handler.sync_vector_index(neo4j_repo)
