"""
RQ Worker 实现模块
"""

from redis import Redis
from rq import Queue, Worker
from rq.registry import ScheduledJobRegistry

from .. import config
from ..utils import LogManager

logger = LogManager.setup_logger("queue_worker")


class QueueWorker:
    """队列工作进程类"""

    def __init__(self):
        """初始化工作进程"""
        try:
            # 连接到 Redis
            self.redis_conn = Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB
            )

            # 设置要监听的队列
            self.queues = [
                Queue(config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=self.redis_conn),
                Queue(config.IMAGE_CONTENT_PROCESS_QUEUE, connection=self.redis_conn)
            ]

            logger.info("工作进程初始化成功")
        except Exception as e:
            logger.error(f"工作进程初始化失败: {e}")
            raise

    def run(self):
        """启动工作进程"""
        try:
            worker = Worker(self.queues)
            logger.info(f"工作进程启动成功，正在监听队列: {[q.name for q in self.queues]}")
            if config.RATE_LIMIT_ENABLED:
                # 启动调度器 https://python-rq.org/docs/scheduling/#running-the-scheduler
                worker.work(with_scheduler=True)
            else:
                worker.work()
        except Exception as e:
            logger.error(f"工作进程运行失败: {e}")
            raise
