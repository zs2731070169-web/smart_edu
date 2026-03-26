import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent.parent

# 加载项目根目录下的 .env 文件（不覆盖已存在的系统环境变量）
load_dotenv(ROOT_DIR / ".env", override=False)

# 模型开放平台配置
NEWCOIN_CONFIG = {
    'url': os.environ.get('NEWCOIN_BASE_URL', 'https://api.newcoin.top/v1'),
    'api_key': os.environ.get('NEWCOIN_API_KEY', ''),
    'temperature': 0.5
}

CLOSEAI_CONFIG = {
    'url': os.environ.get('CLOSEAI_BASE_URL', 'https://api.openai-proxy.org/v1'),
    'api_key': os.environ.get('CLOSEAI_API_KEY', ''),
    'temperature': 0.5
}

# 数据库配置
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'db': os.environ.get('MYSQL_DATABASE', 'smart_edu')
}

NEO4J_CONFIG = {
    'uri': os.environ.get('NEO4J_URI', 'neo4j://localhost:7687'),
    'auth': (
        os.environ.get('NEO4J_USER', 'neo4j'),
        os.environ.get('NEO4J_PASSWORD', '')
    )
}

# Session 密钥
SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY', '')

# 是否开启Memory
AGENT_WITH_MEMORY = os.environ.get('AGENT_WITH_MEMORY', 'true').lower() == 'true'

# 静态资源配置
WEB_DIR = str(ROOT_DIR / "src" / "front")

# 模型
EMBEDDINGS_MODEL = str(ROOT_DIR / "models" / "bge-base-zh-v1.5")
BASE_MODEL = str(ROOT_DIR / "models" / "uie_base_pytorch")
# NLP_DEBERTA_MODEL = str(ROOT_DIR / "models" / "nlp_deberta_rex-uninlu_chinese-base")

# 目录
CHECKPOINT_DIR = ROOT_DIR / "checkpoint"

# 进行实体提取的标签节点
NODE_LIST = ['Course', 'Chapter', 'Question', 'Knowledge', 'Category', 'Paper', 'Subject', 'Video']