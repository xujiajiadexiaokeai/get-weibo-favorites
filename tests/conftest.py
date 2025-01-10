"""测试公共配置和fixture"""

import pytest
import time

@pytest.fixture(scope="session")
def shared_tmp_path(tmp_path_factory):
    """创建一个会话级别的共享临时目录"""
    return tmp_path_factory.mktemp("shared")

@pytest.fixture(autouse=True)
def mock_log_config(monkeypatch, shared_tmp_path):
    """为所有测试配置日志路径
    
    这个fixture会自动应用于所有测试，它会：
    1. 创建临时的测试日志目录
    2. 配置所有日志输出到测试目录
    3. 测试完成后自动清理所有测试日志文件
    """
    test_log_dir = shared_tmp_path / "logs"
    test_log_dir.mkdir(exist_ok=True)
    test_log_file = test_log_dir / "test_app.log"
    test_runs_dir = test_log_dir / "test_runs"
    test_runs_dir.mkdir(exist_ok=True)
    monkeypatch.setattr("weibo_favorites.config.LOG_FILE", test_log_file)
    monkeypatch.setattr("weibo_favorites.config.LOGS_DIR", test_log_dir)
    monkeypatch.setattr("weibo_favorites.config.RUNS_DIR", test_runs_dir)

    # 重置 LogManager 状态
    from weibo_favorites.utils import LogManager
    import logging

    # 清理现有的 handlers
    if LogManager._app_file_handler:
        LogManager._app_file_handler.close()
        LogManager._app_file_handler = None
    
    # 清理所有已存在的logger
    for name in ["scheduler", "crawler", "auth", "database", "queue", "task", "web"]:
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
    LogManager._loggers.clear()

    # 重新设置日志记录器
    LogManager.setup_module_loggers()

    yield

    # 不需要清理测试日志文件，pytest默认只保留最后三次临时目录
    # if test_log_file.exists():
    #     test_log_file.unlink()
    # if test_runs_dir.exists():
    #     for f in test_runs_dir.glob("*"):
    #         f.unlink()
    #     test_runs_dir.rmdir()
    # if test_log_dir.exists():
    #     test_log_dir.rmdir()

# TODO: 移除autouse fixture
@pytest.fixture(autouse=True)
def test_log_config(shared_tmp_path):
    """测试日志配置是否正确生效"""
    from weibo_favorites.utils import LogManager
    # 获取当前的日志文件路径
    logger = LogManager.setup_logger("test_logger")
    handler = logger.handlers[1]  # 第二个handler是文件handler
    log_path = handler.baseFilename

    # 验证日志路径是否正确（应该在临时目录中）
    assert str(shared_tmp_path) in log_path, f"日志文件路径错误: {log_path}"
    
    # 写入一条测试日志
    test_message = "测试日志消息"
    logger.info(test_message)
    
    # 确保日志被刷新到文件
    handler.flush()
    time.sleep(0.1)  # 给文件系统一点时间来完成写入
    
    # 验证日志是否写入到正确的文件
    with open(log_path, 'r', encoding='utf-8') as f:
        log_content = f.read()
        assert test_message in log_content, "日志内容未写入正确的文件"
