import logging
import pymysql
from pymysql.cursors import DictCursor

from backend.config.settings import MYSQL_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("db_conn")


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

