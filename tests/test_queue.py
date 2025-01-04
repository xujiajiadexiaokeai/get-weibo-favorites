"""队列测试模块"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from dotenv import load_dotenv
from rq.job import Job
from rq.registry import FailedJobRegistry

from weibo_favorites import config
from weibo_favorites.crawler.queue import ProcessQueue, LongTextProcessQueue, ImageProcessQueue


@pytest.fixture
def mock_redis():
    """Mock Redis连接"""
    with patch("redis.Redis") as mock:
        yield mock


@pytest.fixture
def mock_queue():
    """Mock Queue对象"""
    with patch("rq.Queue") as mock:
        yield mock


@pytest.fixture
def process_queue(mock_redis, mock_queue):
    """创建基础处理队列实例"""
    return ProcessQueue("test_queue")


@pytest.fixture
def ltp_queue(mock_redis, mock_queue):
    """创建长文本处理队列实例"""
    return LongTextProcessQueue()


@pytest.fixture
def image_queue(mock_redis, mock_queue):
    """创建图片处理队列实例"""
    return ImageProcessQueue()


@pytest.fixture(scope="session")
def load_env():
    """加载环境变量，这个 fixture 只在测试会话开始时执行一次"""
    # 获取项目根目录
    root_dir = Path(__file__).parent.parent
    dotenv_path = root_dir / ".env"

    # 如果 .env 文件存在则加载它
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    else:
        # 如果没有 .env 文件，设置必要的测试环境变量
        os.environ.setdefault("WEIBO_UID", "test_uid")
        os.environ.setdefault(
            "WEIBO_COOKIES_FILE", str(root_dir / "tests/fixtures/test_cookies.json")
        )


@pytest.fixture(autouse=True)
def setup_test_env(load_env):
    """自动使用的 fixture，确保每个测试都在干净的环境中运行"""
    # 保存当前环境变量
    original_env = dict(os.environ)

    yield

    # 恢复原始环境变量
    os.environ.clear()
    os.environ.update(original_env)


class TestProcessQueue:
    """基础处理队列测试类"""

    def test_init_queue(self, mock_redis, mock_queue):
        """测试队列初始化"""
        queue_name = "test_queue"
        process_queue = ProcessQueue(queue_name)

        # 验证Redis连接参数
        mock_redis.assert_called_once_with(
            host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB
        )

        # 验证队列初始化
        mock_queue.assert_called_once_with(
            name=queue_name, connection=mock_redis.return_value
        )

    def test_get_queue_status(self, process_queue: ProcessQueue):
        """测试获取队列状态"""
        # Mock相关方法
        process_queue.queue.__len__ = MagicMock(return_value=5)
        process_queue.failed_registry.__len__ = MagicMock(return_value=2)
        process_queue.finished_registry.__len__ = MagicMock(return_value=3)

        mock_worker = MagicMock()
        mock_worker.state = "busy"
        mock_workers = [mock_worker, MagicMock()]
        with patch("rq.Worker.all", return_value=mock_workers):
            # 执行测试
            status = process_queue.get_queue_status()

        # 验证结果
        assert status["queued_jobs"] == 5
        assert status["failed_jobs"] == 2
        assert status["finished_jobs"] == 3
        assert status["active_workers"] == 1
        assert status["total_workers"] == 2
        assert "last_updated" in status

    def test_get_job_status(self, process_queue: ProcessQueue):
        """测试获取任务状态"""
        # 准备测试数据
        mock_job = MagicMock()
        mock_job.id = "test_job_id"
        mock_job.get_status.return_value = "finished"
        mock_job.exc_info = None
        mock_job.retries_left = 3
        mock_job.enqueued_at = datetime.now()
        mock_job.started_at = datetime.now()
        mock_job.ended_at = datetime.now()
        mock_job.result = {"success": True}

        with patch("rq.job.Job.fetch", return_value=mock_job):
            # 执行测试
            status = process_queue.get_job_status("test_job_id")

        # 验证结果
        assert status["id"] == "test_job_id"
        assert status["status"] == "finished"
        assert status["error"] is None
        assert status["retry_count"] == 3
        assert "enqueued_at" in status
        assert "started_at" in status
        assert "ended_at" in status
        assert status["result"] == {"success": True}

    def test_retry_failed_jobs(self, process_queue: ProcessQueue):
        """测试重试失败任务"""
        # 准备测试数据：创建模拟的失败任务
        mock_jobs = []
        for i in range(2):
            job = MagicMock()
            job.id = f"failed_job_{i}"
            job.retries_left = 2
            mock_jobs.append(job)

        # 设置失败注册表的job_ids
        process_queue.failed_registry.get_job_ids = MagicMock(
            return_value=[job.id for job in mock_jobs]
        )

        # 模拟Job.fetch方法
        with patch("rq.job.Job.fetch", side_effect=mock_jobs):
            # 执行测试
            retry_count = process_queue.retry_failed_jobs()

        # 验证结果
        assert retry_count == len(mock_jobs)
        assert process_queue.queue.enqueue_job.call_count == len(mock_jobs)

    def test_cleanup_jobs(self, process_queue: ProcessQueue):
        """测试清理过期任务"""
        # 准备测试数据：创建模拟的过期任务
        expired_time = datetime.now() - timedelta(days=8)  # 超过保留时间

        mock_failed_jobs = []
        for i in range(2):
            job = MagicMock()
            job.id = f"failed_job_{i}"
            job.ended_at = expired_time
            mock_failed_jobs.append(job)

        mock_finished_jobs = []
        for i in range(1):
            job = MagicMock()
            job.id = f"finished_job_{i}"
            job.ended_at = expired_time
            mock_finished_jobs.append(job)

        # 设置注册表的job_ids
        process_queue.failed_registry.get_job_ids = MagicMock(
            return_value=[job.id for job in mock_failed_jobs]
        )
        process_queue.finished_registry.get_job_ids = MagicMock(
            return_value=[job.id for job in mock_finished_jobs]
        )

        # 模拟Job.fetch方法
        all_jobs = mock_failed_jobs + mock_finished_jobs
        with patch("rq.job.Job.fetch", side_effect=all_jobs):
            # 执行测试
            result = process_queue.cleanup_jobs()

        # 验证结果
        assert result["failed_jobs_cleaned"] == len(mock_failed_jobs)
        assert result["finished_jobs_cleaned"] == len(mock_finished_jobs)

    def test_error_handling(self, process_queue: ProcessQueue):
        """测试错误处理场景"""
        # 测试Redis连接错误
        process_queue.redis.ping.side_effect = Exception("Redis connection error")
        status = process_queue.get_queue_status()
        assert "error" in status
        assert "Redis connection error" in status["error"]

        # 测试获取失败任务详情时的错误
        process_queue.redis.ping.side_effect = None
        process_queue.failed_registry.get_job_ids = MagicMock(return_value=["invalid_job_id"])
        with patch("rq.job.Job.fetch", side_effect=Exception("Job fetch error")):
            status = process_queue.get_queue_status()
            assert len(status["failed_jobs_details"]) == 0


class TestLongTextProcessQueue:
    """长文本处理队列测试类"""

    def test_add_task(self, ltp_queue: LongTextProcessQueue):
        """测试添加任务"""
        # 准备测试数据
        weibo_data = {"id": "123456", "mblogid": "abc123", "is_long_text": True}

        # Mock队列的enqueue方法
        mock_job = MagicMock()
        mock_job.id = "test_job_id"
        ltp_queue.queue.enqueue = MagicMock(return_value=mock_job)

        # 执行测试
        job_id = ltp_queue.add_task(weibo_data)

        # 验证结果
        assert job_id == "test_job_id"
        ltp_queue.queue.enqueue.assert_called_once()

    def test_add_task_not_long_text(self, ltp_queue: LongTextProcessQueue):
        """测试添加非长文本任务"""
        # 准备测试数据
        weibo_data = {"id": "123456", "mblogid": "abc123", "is_long_text": False}

        # Mock队列的enqueue方法
        ltp_queue.queue.enqueue = MagicMock()

        # 执行测试
        job_id = ltp_queue.add_task(weibo_data)

        # 验证结果
        assert job_id is None
        ltp_queue.queue.enqueue.assert_not_called()


class TestImageProcessQueue:
    """图片处理队列测试类"""

    def test_add_task_with_images(self, image_queue: ImageProcessQueue):
        """测试添加带图片的任务"""
        # 准备测试数据
        weibo_data = {
            "idstr": "123456",
            "pic_ids": ["pic1", "pic2"],
            "pic_infos": {
                "pic1": {"mw2000": {
                    "url": "http://example.com/pic1.jpg",
                    "width": 2000,
                    "height": 1500
                }},
                "pic2": {"mw2000": {
                    "url": "http://example.com/pic2.jpg",
                    "width": 2000,
                    "height": 1500
                }}
            }
        }

        # Mock队列的enqueue方法
        mock_job = MagicMock()
        mock_job.id = "test_job_id"
        image_queue.queue.enqueue = MagicMock(return_value=mock_job)

        # 执行测试
        job_ids = image_queue.add_task(weibo_data)

        # 验证结果
        assert len(job_ids) == 2
        assert all(job_id == "test_job_id" for job_id in job_ids)
        assert image_queue.queue.enqueue.call_count == 2

    def test_add_task_no_images(self, image_queue: ImageProcessQueue):
        """测试添加无图片的任务"""
        # 准备测试数据
        weibo_data = {
            "idstr": "123456",
            "pic_ids": [],
            "pic_infos": {}
        }

        # Mock队列的enqueue方法
        image_queue.queue.enqueue = MagicMock()

        # 执行测试
        job_ids = image_queue.add_task(weibo_data)

        # 验证结果
        assert len(job_ids) == 0
        image_queue.queue.enqueue.assert_not_called()

    def test_add_task_missing_mw2000(self, image_queue: ImageProcessQueue):
        """测试添加缺少mw2000尺寸的图片任务"""
        # 准备测试数据
        weibo_data = {
            "idstr": "123456",
            "pic_ids": ["pic1", "pic2"],
            "pic_infos": {
                "pic1": {"mw2000": {
                    "url": "http://example.com/pic1.jpg",
                    "width": 2000,
                    "height": 1500
                }},
                "pic2": {"thumbnail": {"url": "http://example.com/pic2_thumb.jpg"}}  # 缺少mw2000
            }
        }

        # Mock队列的enqueue方法
        mock_job = MagicMock()
        mock_job.id = "test_job_id"
        image_queue.queue.enqueue = MagicMock(return_value=mock_job)

        # 执行测试
        job_ids = image_queue.add_task(weibo_data)

        # 验证结果
        assert len(job_ids) == 1  # 只有一张图片有mw2000尺寸
        assert job_ids[0] == "test_job_id"
        image_queue.queue.enqueue.assert_called_once()

    def test_add_task_invalid_data(self, image_queue: ImageProcessQueue):
        """测试添加无效数据的任务"""
        # 准备测试数据
        invalid_data = {
            "idstr": "123456",
            # 缺少必要的字段
        }

        # Mock队列的enqueue方法
        image_queue.queue.enqueue = MagicMock()

        # 执行测试
        job_ids = image_queue.add_task(invalid_data)

        # 验证结果
        assert len(job_ids) == 0
        image_queue.queue.enqueue.assert_not_called()
