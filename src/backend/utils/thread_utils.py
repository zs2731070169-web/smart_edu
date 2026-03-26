# 执行混合检索的线程池
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("thread_utils")

thread_pool_executor = ThreadPoolExecutor(max_workers=10)
logger.info("线程池初始化完毕...")