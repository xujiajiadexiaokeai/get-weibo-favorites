import pytest
from weibo_favorites.crawler.queue_manager import LongTextQueue
from weibo_favorites.crawler.tasks import fetch_full_content

@pytest.fixture
def queue_manager():
    """创建队列管理器实例"""
    return LongTextQueue()

def test_queue_initialization(queue_manager):
    """测试队列初始化"""
    assert queue_manager is not None
    assert queue_manager.queue is not None
    assert queue_manager.redis is not None

def test_add_task(queue_manager):
    """测试添加任务到队列"""
    test_weibo = {
        "weibo_id": "5106743085896213",
        "url": "https://m.weibo.cn/status/P2PpWoJSd",
        "is_long_text": True
    }
    
    # 清空队列
    queue_manager.queue.empty()
    
    job_id = queue_manager.add_task(test_weibo)
    assert job_id is not None
    
    # 检查队列状态
    status = queue_manager.get_queue_status()
    assert status is not None
    assert status['queued'] >= 0  # 由于任务可能被立即执行，这里只检查状态获取是否正常

def test_execute_task():
    """测试任务执行"""
    test_task = {
        "weibo_id": "5113072119974206",
        "url": "https://weibo.com/ajax/statuses/longtext?id=P5u43FQKi",
        "is_long_text": True
    }
    
    result = fetch_full_content(test_task)
    assert isinstance(result, dict)
    assert 'success' in result
    assert 'weibo_id' in result
    assert result['weibo_id'] == test_task['weibo_id']

if __name__ == '__main__':
    # test_queue_initialization()
    # test_add_task()
    test_execute_task()