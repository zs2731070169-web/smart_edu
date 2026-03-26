from backend.core.db.db_conn import MysqlReader


class MysqlRepo:


    def read_all(self, sql):
        with MysqlReader() as reader:
            reader.cursor.execute(sql)
            return reader.cursor.fetchall()  # 返回所有数据

mysql_repo = MysqlRepo()