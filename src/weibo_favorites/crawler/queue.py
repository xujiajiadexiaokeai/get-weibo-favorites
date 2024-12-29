"""
队列模块，处理长文本微博的爬取队列
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis
import rq
from rq import Queue, Worker
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry

from .. import config
from ..utils import LogManager
from .tasks import fetch_long_text

logger = LogManager.setup_logger("queue")


class LongTextProcessQueue:
    """长文本处理队列"""

    def __init__(self):
        """初始化Redis连接和队列"""
        try:
            # 初始化Redis连接
            self.redis = redis.Redis(
                host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB
            )
            # 初始化队列
            self.queue = rq.Queue(
                name=config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=self.redis
            )
            # 初始化注册表
            self.failed_registry = FailedJobRegistry(queue=self.queue)
            self.finished_registry = FinishedJobRegistry(queue=self.queue)

            logger.info("长文本处理队列初始化成功")
        except Exception as e:
            logger.error(f"初始化Redis连接失败: {e}")
            raise

    def add_task(self, weibo_data):
        """添加长文本处理任务到队列

        Args:
            weibo_data (dict): 微博数据，包含 id, url 等信息
        """
        if not weibo_data.get("is_long_text"):
            logger.info(f"微博 {weibo_data['id']} 不是长文本微博，不需要处理")
            return

        try:
            task_data = {
                "weibo_id": weibo_data["id"],
                "url": config.LONG_TEXT_CONTENT_URL + weibo_data["mblogid"],
                "retry_count": 0,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }

            # 将任务加入队列
            job = self.queue.enqueue(
                fetch_long_text,
                task_data,
                job_timeout="10m",  # 设置任务超时时间为10分钟
                retry=config.MAX_RETRY_COUNT,
                retry_delay=config.RETRY_DELAY,
            )

            logger.info(f"已添加长文本处理任务: {task_data['weibo_id']}, job_id: {job.id}")
            return job.id
        except Exception as e:
            logger.error(f"添加任务到队列失败: {e}")
            return None

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
