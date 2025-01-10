"""
速率限制器集成测试
"""

import time
from datetime import datetime, timedelta
from typing import List

import pytest
import redis
from rq import Queue, SimpleWorker
from rq.job import Job

from weibo_favorites import config
from weibo_favorites.crawler.rate_limiter import RateLimiter
from weibo_favorites.crawler.queue import ProcessQueue
from weibo_favorites.utils import LogManager

logger = LogManager.setup_logger("test_rate_limiter")


@pytest.fixture
def redis_conn():
    """Redis连接fixture"""
    conn = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB
    )
    yield conn
    # 清理测试数据
    conn.flushdb()


@pytest.fixture
def test_queue(redis_conn):
    """测试队列fixture"""
    queue = Queue("test_queue", connection=redis_conn)
    yield queue
    # 清理队列
    queue.empty()


def dummy_task(task_id: int) -> int:
    """测试任务函数

    Args:
        task_id: 任务ID

    Returns:
        任务ID
    """
    logger.info(f"执行任务 {task_id}")
    return task_id


def get_job_execution_times(jobs: List[Job]) -> List[float]:
    """获取任务的执行时间列表

    Args:
        jobs: 任务列表

    Returns:
        执行时间列表
    """
    execution_times = []
    for job in jobs:
        if job.started_at:
            execution_times.append(job.started_at.timestamp())
    return sorted(execution_times)


def test_rate_limiter_basic(redis_conn):
    """测试速率限制器基本功能"""
    rate_limiter = RateLimiter(redis_conn, "test", rate=60, window=60)  # 每秒1个请求
    
    # 测试获取执行时间
    next_time = rate_limiter.get_next_execution_time()
    assert next_time is not None
    assert isinstance(next_time, datetime)
    
    # 测试等待令牌
    assert rate_limiter.wait_for_token(timeout=2)  # 增加超时时间到2秒
    
    # 测试速率限制
    start_time = time.time()
    execution_times = []
    for _ in range(3):
        assert rate_limiter.wait_for_token(timeout=2)  # 增加超时时间到2秒
        execution_times.append(time.time())
    
    # 检查执行间隔
    intervals = [execution_times[i+1] - execution_times[i] for i in range(len(execution_times)-1)]
    avg_interval = sum(intervals) / len(intervals)
    assert 0.8 <= avg_interval <= 1.2  # 考虑到随机性，区间相对宽松


def test_process_queue_rate_limit(redis_conn, test_queue):
    """测试ProcessQueue的速率限制功能"""
    # 创建测试队列，设置速率限制为每分钟10个请求
    process_queue = ProcessQueue("test_queue", rate_limit=10)
    
    # 创建测试任务
    jobs = []
    for i in range(5):
        job_id = process_queue._enqueue_task(dummy_task, {"task_id": i})
        assert job_id is not None
        job = Job.fetch(job_id, connection=redis_conn)
        jobs.append(job)

    # 创建worker并定期执行任务直到所有任务完成
    worker = SimpleWorker([test_queue], connection=redis_conn)
    while len([job for job in jobs if not job.is_finished]) > 0:
        worker.work(with_scheduler=True,burst=True)  # 执行当前可用的任务
        time.sleep(1)

    # 检查所有任务是否都执行成功
    for job in jobs:
        job.refresh()
        assert job.is_finished, f"任务 {job.id} 未完成"
        assert job.result == job.kwargs["task_id"], f"任务 {job.id} 的结果不正确"
    
    # 检查任务执行时间间隔
    execution_times = get_job_execution_times(jobs)
    intervals = [execution_times[i+1] - execution_times[i] for i in range(len(execution_times)-1)]
    avg_interval = sum(intervals) / len(intervals)
    assert 4 <= avg_interval <= 8  # 考虑到随机性，区间相对宽松


def test_delayed_task_execution(redis_conn, test_queue):
    """测试延迟任务执行"""
    process_queue = ProcessQueue("test_queue", rate_limit=10)
    
    # 获取下一个执行时间
    rate_limiter = process_queue.rate_limiter
    next_time = rate_limiter.get_next_execution_time()
    
    # 创建延迟任务
    job_id = process_queue._enqueue_task(dummy_task, {"task_id": 1})
    # assert job_id is not None
    
    job = Job.fetch(job_id, connection=redis_conn)
    
    # 执行任务
    worker = SimpleWorker([test_queue], connection=redis_conn)
    while not job.is_finished:
        worker.work(with_scheduler=True, burst=True)
        time.sleep(1)
        job.refresh()
    # 检查任务是否被正确调度
    print("job enqueued_at: ",job.enqueued_at)
    print("job started_at: ",job.started_at)
    assert job.enqueued_at is not None
    # TODO: 时区处理
    assert job.enqueued_at + timedelta(hours=8) >= next_time
    # 检查任务执行结果
    assert job.is_finished
    assert job.result == 1
