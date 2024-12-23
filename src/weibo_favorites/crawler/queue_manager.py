"""
队列管理模块，处理长文本微博的爬取队列
"""

from datetime import datetime
from redis import Redis
from rq import Queue

from weibo_favorites.crawler.tasks import fetch_long_text
from weibo_favorites.utils import LogManager
from .. import config

logger = LogManager.setup_logger('queue')

class LongTextQueue:
    """长文本处理队列管理器"""
    
    def __init__(self):
        """初始化Redis连接和队列"""
        try:
            self.redis = Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB
            )
            self.queue = Queue(config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=self.redis)
            logger.info("长文本处理队列初始化成功")
        except Exception as e:
            logger.error(f"初始化Redis连接失败: {e}")
            raise
    
    def add_task(self, weibo_data):
        """添加长文本处理任务到队列
        
        Args:
            weibo_data (dict): 微博数据，包含 id, url 等信息
        """
        if not weibo_data.get('is_long_text'):
            return
            
        try:
            task_data = {
                'weibo_id': weibo_data['id'],
                'url': config.LONG_TEXT_CONTENT_URL + weibo_data['mblogid'],
                'retry_count': 0,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            # 将任务加入队列
            job = self.queue.enqueue(
                fetch_long_text,
                task_data,
                job_timeout='10m'  # 设置任务超时时间为10分钟
            )
            
            logger.info(f"已添加长文本处理任务: {task_data['weibo_id']}, job_id: {job.id}")
            return job.id
            
        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            raise
    
    def get_queue_status(self):
        """获取队列状态信息"""
        try:
            return {
                'queued': self.queue.count,
                'failed': len(self.queue.failed_job_registry),
                'running': len(self.queue.started_job_registry)
            }
        except Exception as e:
            logger.error(f"获取队列状态失败: {e}")
            return None
