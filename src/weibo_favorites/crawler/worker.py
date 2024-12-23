"""
长文本处理工作进程
"""
import sys
from redis import Redis
from rq import Worker

from .. import config
from ..utils import LogManager

# 设置日志记录器
logger = LogManager.setup_logger('worker')

def main():
    """启动工作进程"""
    try:
        # 连接到Redis
        redis_conn = Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB
        )
        
        # 设置队列名称
        queue_name = config.LONG_TEXT_CONTENT_PROCESS_QUEUE
        
        # 启动工作进程
        w = Worker([queue_name], connection=redis_conn)
        w.work()
        logger.info(f"工作进程已启动，监听队列: {queue_name}")
    except KeyboardInterrupt:
        redis_conn.connection_pool.disconnect()
        logger.info("收到终止信号，工作进程停止运行")
    except Exception as e:
        logger.error(f"工作进程启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
