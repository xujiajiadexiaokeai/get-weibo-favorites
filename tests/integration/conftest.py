"""
集成测试的共享 fixtures
"""

import pytest
import redis
from rq import Queue

from weibo_favorites import config


@pytest.fixture(scope="session")
def redis_conn():
    """Redis连接fixture，会话级别"""
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
    """测试队列fixture，函数级别"""
    queue = Queue("test_queue", connection=redis_conn)
    yield queue
    # 清理队列
    queue.empty()
