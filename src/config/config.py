from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent

# 模型开放平台配置
NEWCOIN_CONFIG = {
    'url': 'https://api.newcoin.top/v1',
    'api_key': 'sk-397oYfn2vpKslUtYVug40peUycE7zdbGsx2JwwrE7x2tah6W'
}

# 数据库配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'smart_edu'
}
NEO4J_CONFIG = {
    'uri': 'neo4j://localhost:7687',
    'auth': ('neo4j', '12345678')
}

# 静态资源配置
WEB_DIR = ROOT_DIR / "src" / "backend" / "web"

# 模型
EMBEDDINGS_MODEL = str(ROOT_DIR / "models" / "bge-base-zh-v1.5")
BASE_MODEL = str(ROOT_DIR / "models" / "uie_base_pytorch")
NLP_DEBERTA_MODEL = str(ROOT_DIR / "models" / "nlp_deberta_rex-uninlu_chinese-base")

# 目录
CHECKPOINT_DIR = ROOT_DIR / "checkpoint"