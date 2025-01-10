import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest

from weibo_favorites.crawler.scheduler import Scheduler
from weibo_favorites.crawler.queue import LongTextProcessQueue, ImageProcessQueue
from weibo_favorites.crawler.auth import CookieManager


@pytest.fixture
def mock_queues():
    """模拟队列对象"""
    ltp_queue = MagicMock(spec=LongTextProcessQueue)
    img_queue = MagicMock(spec=ImageProcessQueue)
    return ltp_queue, img_queue


@pytest.fixture
def mock_files(tmp_path):
    """模拟状态文件"""
    pid_file = tmp_path / "scheduler.pid"
    status_file = tmp_path / "scheduler.status"
    return pid_file, status_file


@pytest.fixture
def mock_run_logger():
    """Mock RunLogger instance"""
    run_logger = MagicMock()
    run_logger.start_new_run.return_value = "test_run_id"
    return run_logger


@pytest.fixture
def scheduler(mock_queues, mock_files, mock_run_logger, monkeypatch):
    """创建调度器实例"""
    ltp_queue, img_queue = mock_queues
    pid_file, status_file = mock_files

    # 模拟配置
    monkeypatch.setattr("weibo_favorites.config.SCHEDULER_PID_FILE", pid_file)
    monkeypatch.setattr("weibo_favorites.config.SCHEDULER_STATUS_FILE", status_file)
    monkeypatch.setattr("weibo_favorites.config.CRAWL_INTERVAL", 300)
    monkeypatch.setattr("weibo_favorites.config.QUEUE_CLEANUP_INTERVAL", 3600)

    # Mock RunLogger and LogManager
    with patch('weibo_favorites.crawler.scheduler.RunLogger', return_value=mock_run_logger), \
         patch('weibo_favorites.crawler.scheduler.LogManager.setup_run_logging'), \
         patch('weibo_favorites.crawler.scheduler.LogManager.cleanup_run_logging'), \
         patch('weibo_favorites.crawler.scheduler.LongTextProcessQueue', return_value=ltp_queue), \
         patch('weibo_favorites.crawler.scheduler.ImageProcessQueue', return_value=img_queue):
        scheduler = Scheduler()
        yield scheduler


def test_init(scheduler, mock_files):
    """测试调度器初始化"""
    pid_file, status_file = mock_files
    assert scheduler.running == False
    assert scheduler.thread is None
    assert scheduler.next_run_time is None
    assert scheduler.run_interval == 300
    assert scheduler.pid_file == pid_file
    assert scheduler.status_file == status_file


def test_is_running_no_pid_file(scheduler):
    """测试调度器未运行状态（无PID文件）"""
    assert scheduler.is_running() == False


def test_is_running_with_pid_file(scheduler, mock_files):
    """测试调度器运行状态（有PID文件）"""
    pid_file, _ = mock_files
    pid = os.getpid()
    pid_file.write_text(str(pid))
    assert scheduler.is_running() == True


def test_is_running_invalid_pid(scheduler, mock_files):
    """测试调度器状态（无效PID）"""
    pid_file, _ = mock_files
    pid_file.write_text("99999999")  # 使用一个不太可能存在的PID
    assert scheduler.is_running() == False


def test_start_already_running(scheduler, mock_files):
    """测试启动已运行的调度器"""
    pid_file, _ = mock_files
    pid = os.getpid()
    pid_file.write_text(str(pid))
    
    cookie_manager = MagicMock(spec=CookieManager)
    assert scheduler.start(cookie_manager) == False


@patch('time.sleep', return_value=None)  # 避免实际的等待
def test_start_with_invalid_cookie(mock_sleep, scheduler, mock_files, mock_run_logger):
    """测试使用无效cookie启动调度器"""
    cookie_manager = MagicMock(spec=CookieManager)
    cookie_manager.check_validity.return_value = (False, "Cookie已过期")
    
    start_time = time.time()
    
    # 模拟一次循环后停止
    def stop_after_one_loop(*args, **kwargs):
        scheduler.running = False
    mock_sleep.side_effect = stop_after_one_loop
    
    scheduler.start(cookie_manager)
    
    # 验证RunLogger交互
    mock_run_logger.start_new_run.assert_called_once()
    mock_run_logger.update_run.assert_called_once_with(
        "test_run_id",
        status="error",
        error="Cookie无效",
        end_time=ANY  # 使用ANY匹配器因为时间戳是动态的
    )
    
    # 验证等待逻辑
    mock_sleep.assert_called_once()
    args = mock_sleep.call_args[0]
    assert 0 <= args[0] <= scheduler.run_interval, "等待时间应该在0到run_interval之间"


@patch('time.sleep', return_value=None)
def test_start_successful_crawl(mock_sleep, scheduler, mock_files):
    """测试成功爬取的情况"""
    cookie_manager = MagicMock(spec=CookieManager)
    cookie_manager.check_validity.return_value = (True, None)
    session = MagicMock()
    cookie_manager.create_session.return_value = session

    with patch('weibo_favorites.crawler.scheduler.crawl_favorites') as mock_crawl:
        mock_crawl.return_value = [{"id": 1}, {"id": 2}]
        
        def stop_after_one_loop(*args, **kwargs):
            scheduler.running = False
        mock_sleep.side_effect = stop_after_one_loop
        
        assert scheduler.start(cookie_manager) == True


def test_stop_not_running(scheduler):
    """测试停止未运行的调度器"""
    assert scheduler.stop() == False


def test_stop_running(scheduler, mock_files):
    """测试停止运行中的调度器"""
    pid_file, _ = mock_files
    pid = os.getpid()
    pid_file.write_text(str(pid))

    with patch('os.kill') as mock_kill, \
         patch('os.waitpid') as mock_waitpid:
        mock_waitpid.return_value = (pid, 0)
        assert scheduler.stop() == True
        
        # 验证kill被调用了两次：一次是检查进程存在(signal 0)，一次是终止进程(signal 15)
        assert mock_kill.call_count == 2
        assert mock_kill.call_args_list == [
            ((pid, 0),),  # 第一次调用，检查进程
            ((pid, 15),), # 第二次调用，终止进程
        ]


def test_cleanup_queues_success(scheduler, mock_queues):
    """测试成功清理队列"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟返回值
    ltp_queue.cleanup_jobs.return_value = 5
    img_queue.cleanup_jobs.return_value = 3

    # 执行清理
    result = scheduler.cleanup_queues()

    # 验证结果
    assert result["long_text_cleaned"] == 5
    assert result["image_cleaned"] == 3
    assert "cleaned_at" in result
    assert len(result["errors"]) == 0

    # 验证调用
    ltp_queue.cleanup_jobs.assert_called_once()
    img_queue.cleanup_jobs.assert_called_once()


def test_cleanup_queues_with_errors(scheduler, mock_queues):
    """测试清理队列时出现错误"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟异常
    ltp_queue.cleanup_jobs.side_effect = Exception("长文本队列错误")
    img_queue.cleanup_jobs.side_effect = Exception("图片队列错误")

    # 执行清理
    result = scheduler.cleanup_queues()

    # 验证结果
    assert result["long_text_cleaned"] == 0
    assert result["image_cleaned"] == 0
    assert len(result["errors"]) == 2
    assert "长文本队列错误" in result["errors"][0]
    assert "图片队列错误" in result["errors"][1]


def test_retry_failed_jobs_success(scheduler, mock_queues):
    """测试成功重试失败任务"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟返回值
    ltp_queue.retry_failed_jobs.return_value = 2
    img_queue.retry_failed_jobs.return_value = 1

    # 执行重试
    result = scheduler.retry_failed_jobs()

    # 验证结果
    assert result["long_text_retried"] == 2
    assert result["image_retried"] == 1
    assert "retried_at" in result
    assert len(result["errors"]) == 0

    # 验证调用
    ltp_queue.retry_failed_jobs.assert_called_once()
    img_queue.retry_failed_jobs.assert_called_once()


def test_retry_failed_jobs_with_errors(scheduler, mock_queues):
    """测试重试失败任务时出现错误"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟异常
    ltp_queue.retry_failed_jobs.side_effect = Exception("长文本重试错误")
    img_queue.retry_failed_jobs.side_effect = Exception("图片重试错误")

    # 执行重试
    result = scheduler.retry_failed_jobs()

    # 验证结果
    assert result["long_text_retried"] == 0
    assert result["image_retried"] == 0
    assert len(result["errors"]) == 2
    assert "长文本重试错误" in result["errors"][0]
    assert "图片重试错误" in result["errors"][1]


def test_deprecated_cleanup_queue(scheduler, mock_queues):
    """测试废弃的_cleanup_queue方法"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟返回值
    ltp_queue.cleanup_jobs.return_value = 3
    img_queue.cleanup_jobs.return_value = 2
    ltp_queue.retry_failed_jobs.return_value = 1
    img_queue.retry_failed_jobs.return_value = 1

    # 执行清理
    cleanup_result, retry_result = scheduler._cleanup_queue()

    # 验证结果
    assert cleanup_result["long_text_cleaned"] == 3
    assert cleanup_result["image_cleaned"] == 2
    assert retry_result["long_text_retried"] == 1
    assert retry_result["image_retried"] == 1

    # 验证调用
    ltp_queue.cleanup_jobs.assert_called_once()
    img_queue.cleanup_jobs.assert_called_once()
    ltp_queue.retry_failed_jobs.assert_called_once()
    img_queue.retry_failed_jobs.assert_called_once()


def test_check_queue_status(scheduler, mock_queues):
    """测试检查队列状态"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟返回值
    ltp_queue.get_queue_status.return_value = {
        "active_workers": 2,
        "pending_jobs": 5
    }
    img_queue.get_queue_status.return_value = {
        "active_workers": 1,
        "pending_jobs": 3
    }

    # 执行状态检查
    result = scheduler.check_queue_status()

    # 验证结果
    assert result["long_text_queue"]["active_workers"] == 2
    assert result["long_text_queue"]["pending_jobs"] == 5
    assert result["image_queue"]["active_workers"] == 1
    assert result["image_queue"]["pending_jobs"] == 3
    assert "last_checked" in result

    # 验证调用
    ltp_queue.get_queue_status.assert_called_once()
    img_queue.get_queue_status.assert_called_once()


def test_check_queue_status_no_workers(scheduler, mock_queues):
    """测试检查队列状态时没有活跃worker"""
    ltp_queue, img_queue = mock_queues
    
    # 设置模拟返回值
    ltp_queue.get_queue_status.return_value = {
        "active_workers": 0,
        "pending_jobs": 5
    }
    img_queue.get_queue_status.return_value = {
        "active_workers": 0,
        "pending_jobs": 3
    }

    # 执行状态检查
    result = scheduler.check_queue_status()

    # 验证结果
    assert result["long_text_queue"]["active_workers"] == 0
    assert result["image_queue"]["active_workers"] == 0
    assert "last_checked" in result

    # 验证调用
    ltp_queue.get_queue_status.assert_called_once()
    img_queue.get_queue_status.assert_called_once()


def test_get_status_not_running(scheduler):
    """测试获取未运行状态的调度器状态"""
    status = scheduler.get_status()
    assert status["running"] == False
    assert "current_time" in status
    assert status["next_run"] is None
    assert status["interval"] == 300


def test_get_status_running(scheduler, mock_files):
    """测试获取运行中的调度器状态"""
    pid_file, status_file = mock_files
    
    # 设置PID文件来模拟运行状态
    pid = os.getpid()
    pid_file.write_text(str(pid))
    
    test_status = {
        "running": True,
        "current_time": datetime.now().isoformat(),
        "next_run": (datetime.now() + timedelta(seconds=300)).isoformat(),
        "interval": 300
    }
    status_file.write_text(json.dumps(test_status))
    
    # 确保调度器处于运行状态
    scheduler.running = True
    
    status = scheduler.get_status()
    assert status["running"] == True
    assert status["next_run"] == test_status["next_run"]
    assert status["interval"] == 300


def test_update_status(scheduler, mock_files):
    """测试更新调度器状态"""
    _, status_file = mock_files
    scheduler.running = True
    scheduler.next_run_time = datetime.now() + timedelta(seconds=300)
    
    scheduler._update_status()
    
    assert status_file.exists()
    status = json.loads(status_file.read_text())
    assert status["running"] == True
    assert "next_run" in status
    assert status["interval"] == 300


def test_cleanup_files(scheduler, mock_files):
    """测试清理状态文件"""
    pid_file, status_file = mock_files
    
    # 创建测试文件
    pid_file.write_text("12345")
    status_file.write_text("{}")
    
    scheduler._cleanup_files()
    
    assert not pid_file.exists()
    assert not status_file.exists()


@patch('time.sleep', return_value=None)
@patch('weibo_favorites.crawler.scheduler.crawl_favorites')
def test_start_successful_run(mock_crawl, mock_sleep, scheduler, mock_files, mock_run_logger):
    """测试成功启动并执行一次任务"""
    cookie_manager = MagicMock(spec=CookieManager)
    cookie_manager.check_validity.return_value = (True, None)
    cookie_manager.create_session.return_value = MagicMock()
    
    # 模拟爬虫返回数据
    mock_crawl.return_value = [{"id": 1}, {"id": 2}]
    start_time = time.time()
    
    # 模拟一次循环后停止
    def stop_after_one_loop(*args, **kwargs):
        scheduler.running = False
    mock_sleep.side_effect = stop_after_one_loop
    
    scheduler.start(cookie_manager)
    
    # 验证RunLogger交互
    mock_run_logger.start_new_run.assert_called_once()
    mock_run_logger.update_run.assert_called_once_with(
        "test_run_id",
        status="success",
        items_count=2,
        end_time=ANY
    )
    
    # 验证其他组件交互
    mock_crawl.assert_called_once()
    
    # 验证等待逻辑
    mock_sleep.assert_called_once()
    args = mock_sleep.call_args[0]
    assert 0 <= args[0] <= scheduler.run_interval, "等待时间应该在0到run_interval之间"
