"""队列测试模块"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from rq.job import Job
from rq.registry import FailedJobRegistry

from weibo_favorites import config
from weibo_favorites.crawler.queue import LongTextProcessQueue
from weibo_favorites.crawler.tasks import fetch_long_text


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
def ltp_queue(mock_redis, mock_queue):
    """创建队列管理器实例"""
    return LongTextProcessQueue()


def test_unit_init_queue(mock_redis, mock_queue):
    """测试队列初始化"""
    ltp_queue = LongTextProcessQueue()

    # 验证Redis连接参数
    mock_redis.assert_called_once_with(
        host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB
    )

    # 验证队列初始化
    mock_queue.assert_called_once_with(
        name=config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=mock_redis.return_value
    )


def test_unit_add_task(ltp_queue: LongTextProcessQueue):
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


def test_unit_add_task_not_long_text(ltp_queue: LongTextProcessQueue):
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


def test_unit_get_queue_status(ltp_queue: LongTextProcessQueue):
    """测试获取队列状态"""
    # Mock相关方法
    ltp_queue.queue.__len__ = MagicMock(return_value=5)
    ltp_queue.failed_registry.__len__ = MagicMock(return_value=2)
    ltp_queue.finished_registry.__len__ = MagicMock(return_value=3)

    mock_worker = MagicMock()
    mock_worker.state = "busy"
    mock_workers = [mock_worker, MagicMock()]
    with patch("rq.Worker.all", return_value=mock_workers):
        # 执行测试
        status = ltp_queue.get_queue_status()

    # 验证结果
    assert status["queued_jobs"] == 5
    assert status["failed_jobs"] == 2
    assert status["finished_jobs"] == 3
    assert status["active_workers"] == 1
    assert status["total_workers"] == 2
    assert "last_updated" in status


def test_unit_retry_failed_jobs(ltp_queue: LongTextProcessQueue):
    """测试重试失败任务"""
    # 准备测试数据：创建模拟的失败任务
    mock_jobs = []
    for i in range(2):
        job = MagicMock()
        job.id = f"failed_job_{i}"
        job.retries_left = 2
        mock_jobs.append(job)

    # 设置失败注册表的job_ids
    ltp_queue.failed_registry.get_job_ids = MagicMock(
        return_value=[job.id for job in mock_jobs]
    )

    # 模拟Job.fetch方法
    with patch("rq.job.Job.fetch", side_effect=mock_jobs):
        # 执行测试
        retry_count = ltp_queue.retry_failed_jobs()

    # 验证结果
    assert retry_count == len(mock_jobs)
    assert ltp_queue.queue.enqueue_job.call_count == len(mock_jobs)


def test_unit_cleanup_jobs(ltp_queue: LongTextProcessQueue):
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
    ltp_queue.failed_registry.get_job_ids = MagicMock(
        return_value=[job.id for job in mock_failed_jobs]
    )
    ltp_queue.finished_registry.get_job_ids = MagicMock(
        return_value=[job.id for job in mock_finished_jobs]
    )

    # 模拟Job.fetch方法
    all_jobs = mock_failed_jobs + mock_finished_jobs
    with patch("rq.job.Job.fetch", side_effect=all_jobs):
        # 执行测试
        result = ltp_queue.cleanup_jobs()

    # 验证结果
    assert result["failed_jobs_cleaned"] == len(mock_failed_jobs)
    assert result["finished_jobs_cleaned"] == len(mock_finished_jobs)
    # 验证每个任务都被删除了
    for job in all_jobs:
        job.delete.assert_called_once()


def test_unit_get_job_status(ltp_queue: LongTextProcessQueue):
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
        status = ltp_queue.get_job_status("test_job_id")

    # 验证结果
    assert status["id"] == "test_job_id"
    assert status["status"] == "finished"
    assert status["error"] is None
    assert status["retry_count"] == 3
    assert "enqueued_at" in status
    assert "started_at" in status
    assert "ended_at" in status
    assert status["result"] == {"success": True}


def test_unit_error_handling(ltp_queue: LongTextProcessQueue):
    """测试错误处理场景"""
    # 场景1：Redis连接失败
    ltp_queue.redis.ping = MagicMock(side_effect=Exception("Connection failed"))

    # 测试获取队列状态时的错误处理
    status = ltp_queue.get_queue_status()
    assert "error" in status
    assert "Connection failed" in status["error"]
    assert "last_updated" in status
    assert len(status.keys()) == 2  # 只应包含 error 和 last_updated

    # 场景2：队列操作失败
    weibo_data = {"id": "123", "mblogid": "abc123", "is_long_text": True}
    ltp_queue.queue.enqueue = MagicMock(side_effect=Exception("Enqueue failed"))
    job_id = ltp_queue.add_task(weibo_data)
    assert job_id is None

    # 场景3：获取失败任务详情时出错
    ltp_queue.redis.ping = MagicMock()  # 重置 ping 方法
    ltp_queue.failed_registry.get_job_ids = MagicMock(return_value=["job1"])
    Job.fetch = MagicMock(side_effect=Exception("Failed to fetch job"))
    FailedJobRegistry.get_job_count = MagicMock(return_value=1)  # 模拟返回一个失败任务
    status = ltp_queue.get_queue_status()
    assert "failed_jobs_details" in status
    assert status["failed_jobs"] == 1
    assert len(status["failed_jobs_details"]) == 0  # 由于获取失败，列表应为空
    assert "error" not in status  # 单个任务获取失败不应影响整体状态


# TODO: 集成测试(暂时不测试,稍后修改)
# def test_integration_add_task(ltp_queue: LongTextProcessQueue):
#     """测试添加任务到队列"""
#     test_weibo = {
#         "weibo_id": "5113072119974206",
#         "url": "https://weibo.com/ajax/statuses/longtext?id=P5u43FQKi",
#         "is_long_text": True
#     }

#     # 清空队列
#     ltp_queue.queue.empty()

#     job_id = ltp_queue.add_task(test_weibo)
#     assert job_id is not None

#     # 检查队列状态
#     status = ltp_queue.get_queue_status()
#     assert status is not None
#     assert status['queued'] >= 0  # 由于任务可能被立即执行，这里只检查状态获取是否正常

# def test_integration_execute_task():
#     """测试任务执行"""
#     test_task = {
#         "weibo_id": "5113072119974206",
#         "url": "https://weibo.com/ajax/statuses/longtext?id=P5u43FQKi",
#         "is_long_text": True
#     }

#     result = fetch_long_text(test_task)
#     assert isinstance(result, dict)
#     assert 'success' in result
#     assert 'weibo_id' in result
#     assert result['weibo_id'] == test_task['weibo_id']
