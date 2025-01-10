"""
队列模块，处理微博内容的爬取队列
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

import redis
import rq
from rq import Queue, Worker
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry

from .. import config
from ..utils import LogManager
from .tasks import fetch_long_text, process_image_content
from .rate_limiter import RateLimiter

logger = LogManager.setup_logger("queue")


class ProcessQueue:
    """基础处理队列类"""

    def __init__(
        self,
        queue_name: str,
        rate_limit: Optional[int] = None
    ):
        """初始化Redis连接和队列

        Args:
            queue_name: 队列名称
            rate_limit: 速率限制（每分钟请求数），None表示不限制
        """
        try:
            # 初始化Redis连接
            self.redis = redis.Redis(
                host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB
            )
            # 初始化队列
            self.queue = rq.Queue(
                name=queue_name, connection=self.redis
            )
            # 初始化注册表
            self.failed_registry = FailedJobRegistry(queue=self.queue)
            self.finished_registry = FinishedJobRegistry(queue=self.queue)
            
            # 初始化速率限制器
            self.rate_limiter = None
            if config.RATE_LIMIT_ENABLED and rate_limit:
                self.rate_limiter = RateLimiter(
                    self.redis,
                    queue_name,
                    rate_limit,
                    config.RATE_LIMIT_WINDOW
                )

            logger.info(f"{queue_name} 队列初始化成功")
        except Exception as e:
            logger.error(f"初始化Redis连接失败: {e}")
            raise

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态

        Returns:
            队列状态信息
        """
        status = {"last_updated": datetime.now().isoformat()}

        try:
            # 检查Redis连接
            self.redis.ping()

            workers = Worker.all(connection=self.redis)
            active_workers = [w for w in workers if w.state == "busy"]

            status.update(
                {
                    "queued_jobs": len(self.queue),
                    "failed_jobs": self.failed_registry.__len__(),
                    "finished_jobs": self.finished_registry.__len__(),
                    "active_workers": len(active_workers),
                    "total_workers": len(workers),
                }
            )
            # 获取失败任务详情
            failed_jobs = []
            for job_id in self.failed_registry.get_job_ids():
                logger.info(f"获取失败任务详情: {job_id}")
                try:
                    job = Job.fetch(job_id, connection=self.redis)
                    failed_jobs.append(
                        {
                            "id": job.id,
                            "status": job.get_status(),
                            "retry_count": job.retries_left,
                        }
                    )
                except Exception as e:
                    logger.error(f"获取失败任务详情出错: {e}")
                    continue
            status["failed_jobs_details"] = failed_jobs
            logger.info(f"队列状态: {status}")

        except Exception as e:
            error_msg = f"获取队列状态失败: {str(e)}"
            logger.error(error_msg)
            status["error"] = error_msg

        return status

    def retry_failed_jobs(self) -> int:
        """重试失败的任务

        Returns:
            重试的任务数量
        """
        count = 0
        try:
            for job_id in self.failed_registry.get_job_ids():
                job = Job.fetch(job_id, connection=self.redis)
                logger.info(f"重试失败任务: {job_id}")
                if job.retries_left > 0:
                    self.queue.enqueue_job(job)
                    count += 1
            logger.info(f"重试 {count} 个失败任务")
            return count
        except Exception as e:
            logger.error(f"重试失败任务时出错: {e}")
            return count

    def cleanup_jobs(self) -> Dict[str, int]:
        """清理过期的任务

        Returns:
            清理的任务数量
        """
        try:
            # 清理失败任务
            failed_count = 0
            failed_cutoff = datetime.now() - timedelta(
                seconds=config.FAILED_JOBS_RETENTION
            )
            for job_id in self.failed_registry.get_job_ids():
                job = Job.fetch(job_id, connection=self.redis)
                if job.ended_at and job.ended_at < failed_cutoff:
                    job.delete()
                    failed_count += 1
                    logger.info(f"清理失败任务: {job_id}")

            # 清理完成任务
            finished_count = 0
            finished_cutoff = datetime.now() - timedelta(
                seconds=config.FINISHED_JOBS_RETENTION
            )
            for job_id in self.finished_registry.get_job_ids():
                job = Job.fetch(job_id, connection=self.redis)
                if job.ended_at and job.ended_at < finished_cutoff:
                    job.delete()
                    finished_count += 1
                    logger.info(f"清理完成任务: {job_id}")

            logger.info(f"清理 {failed_count} 个失败任务，{finished_count} 个完成任务")
            return {
                "failed_jobs_cleaned": failed_count,
                "finished_jobs_cleaned": finished_count,
            }
        except Exception as e:
            logger.error(f"清理任务时出错: {e}")
            return {
                "failed_jobs_cleaned": 0,
                "finished_jobs_cleaned": 0,
                "error": str(e),
            }

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态

        Args:
            job_id: 任务ID

        Returns:
            任务状态信息
        """
        try:
            job = Job.fetch(job_id, connection=self.redis)
            return {
                "id": job.id,
                "status": job.get_status(),
                "error": str(job.exc_info) if job.exc_info else None,
                "retry_count": job.retries_left,
                "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                "result": job.result,
            }
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None

    def _enqueue_task(self, task_func, task_data: Dict[str, Any], job_timeout: str = "10m") -> Optional[str]:
        """将任务加入队列

        Args:
            task_func: 任务处理函数
            task_data: 任务数据
            job_timeout: 任务超时时间

        Returns:
            任务ID，如果添加失败则返回None
        """
        try:
            # 获取下一个执行时间
            next_time = self.rate_limiter.get_next_execution_time() if self.rate_limiter else None
            
            # 创建任务
            if next_time and next_time > datetime.now():
                # 计算延迟时间
                delay = (next_time - datetime.now()).total_seconds()
                job = self.queue.enqueue_in(
                    timedelta(seconds=delay),
                    task_func,
                    kwargs={"task_data": task_data},
                    job_timeout=job_timeout
                )
                logger.info(f"任务 {job.id} 已添加到队列，将在 {next_time} 执行")
            else:
                # 立即执行
                job = self.queue.enqueue(
                    task_func,
                    kwargs={"task_data": task_data},
                    job_timeout=job_timeout
                )
                logger.info(f"任务 {job.id} 已添加到队列，立即执行")
            
            return job.id
        except Exception as e:
            logger.error(f"添加任务到队列失败: {e}")
            return None


class LongTextProcessQueue(ProcessQueue):
    """长文本处理队列"""

    def __init__(self):
        """初始化长文本处理队列"""
        super().__init__(config.LONG_TEXT_CONTENT_PROCESS_QUEUE, config.LONG_TEXT_RATE_LIMIT)

    def add_task(self, weibo_data: Dict[str, Any]) -> Optional[str]:
        """添加长文本处理任务到队列

        Args:
            weibo_data: 微博数据，包含 id, url 等信息

        Returns:
            任务ID
        """
        if not weibo_data.get("is_long_text"):
            logger.info(f"微博 {weibo_data['id']} 不是长文本微博，不需要处理")
            return None

        task_data = {
            "weibo_id": weibo_data["id"],
            "url": config.LONG_TEXT_CONTENT_URL + weibo_data["mblogid"],
            "retry_count": 0,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        return self._enqueue_task(fetch_long_text, task_data)


class ImageProcessQueue(ProcessQueue):
    """图片处理队列"""

    def __init__(self):
        """初始化图片处理队列"""
        super().__init__(config.IMAGE_PROCESS_QUEUE, config.IMAGE_RATE_LIMIT)

    def add_task(self, weibo_data: Dict[str, Any]) -> List[str]:
        """添加图片处理任务到队列

        Args:
            weibo_data: 微博数据，包含图片信息

        Returns:
            任务ID列表
        """
        job_ids = []

        pic_infos = weibo_data.get("pic_infos", {})
        pic_ids = weibo_data.get("pic_ids", [])

        for pic_id in pic_ids:
            pic_info = pic_infos.get(pic_id)
            if not pic_info:
                logger.warning(f"图片 {pic_id} 信息不完整")
                continue

            # 检查是否有mw2000尺寸的图片信息
            mw2000 = pic_info.get("mw2000")
            if not mw2000:
                logger.warning(f"图片 {pic_id} 缺少mw2000尺寸")
                continue

            # 检查必要的图片属性
            if not all(key in mw2000 for key in ["url", "width", "height"]):
                logger.warning(f"图片 {pic_id} mw2000尺寸信息不完整")
                continue

            # 构建任务数据
            task_data = {
                "weibo_id": weibo_data["id"],
                "pic_id": pic_id,
                "url": mw2000["url"],
                "width": mw2000["width"],
                "height": mw2000["height"],
                "retry_count": 0,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }

            job_id = self._enqueue_task(process_image_content, task_data)
            if job_id:
                job_ids.append(job_id)
                logger.info(f"已添加图片处理任务: {pic_id}, job_id: {job_id}")

        return job_ids
