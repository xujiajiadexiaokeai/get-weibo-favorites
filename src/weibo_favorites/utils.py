"""工具模块，提供日志和其他通用功能"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

from . import config


class LogManager:
    """日志管理器，统一管理所有模块的日志配置"""

    _loggers: Dict[str, logging.Logger] = {}
    _run_file_handler: Optional[logging.FileHandler] = None
    _current_run_id: Optional[str] = None
    _app_file_handler: Optional[logging.FileHandler] = None

    @classmethod
    def _get_formatter(cls) -> logging.Formatter:
        """获取日志格式化器"""
        return logging.Formatter(config.LOG_FORMAT)

    @classmethod
    def _ensure_app_file_handler(cls) -> None:
        """确保应用日志文件处理器存在"""
        if not cls._app_file_handler:
            # 创建应用日志文件处理器
            log_file = Path(config.LOG_FILE)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            cls._app_file_handler = logging.FileHandler(log_file, encoding="utf-8")
            cls._app_file_handler.setFormatter(cls._get_formatter())
            cls._app_file_handler.setLevel(logging.INFO)

    @classmethod
    def setup_logger(
        cls,
        name: Optional[str] = None,
        log_file: Optional[Union[str, Path]] = None,
        log_level: Optional[str] = None,
    ) -> logging.Logger:
        """设置单个日志记录器

        Args:
            name: 日志记录器名称，默认使用模块名
            log_file: 日志文件路径，默认使用config.LOG_FILE
            log_level: 日志级别，默认使用config.LOG_LEVEL

        Returns:
            配置好的日志记录器
        """
        name = name or __name__

        # 如果已经配置过，直接返回
        if name in cls._loggers:
            return cls._loggers[name]

        # 配置日志记录器
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level or config.LOG_LEVEL))

        if not logger.handlers:  # 避免重复添加处理器
            # 确保应用日志文件处理器存在
            cls._ensure_app_file_handler()

            # 创建控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(cls._get_formatter())
            console_handler.setLevel(getattr(logging, log_level or config.LOG_LEVEL))

            # 添加处理器到日志记录器
            logger.addHandler(console_handler)
            logger.addHandler(cls._app_file_handler)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def setup_module_loggers(cls) -> Dict[str, logging.Logger]:
        """设置所有模块的日志记录器

        Returns:
            包含所有模块日志记录器的字典
        """
        # 创建并配置各个模块的logger
        for name in [
            "scheduler",
            "crawler",
            "auth",
            "database",
            "queue",
            "task",
            "web",
        ]:
            if name not in cls._loggers:
                cls.setup_logger(name)

        return cls._loggers

    @classmethod
    def setup_run_logging(cls, run_id: str) -> None:
        """设置运行日志

        Args:
            run_id: 运行ID
        """
        # 如果已有日志处理器，先移除
        cls.cleanup_run_logging()

        # 设置新的日志文件
        log_path = Path(config.LOGS_DIR) / "runs" / f"run_{run_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cls._run_file_handler = logging.FileHandler(log_path)
        cls._run_file_handler.setFormatter(cls._get_formatter())
        cls._run_file_handler.setLevel(logging.INFO)

        # 添加文件处理器到所有相关的logger
        for logger in cls._loggers.values():
            logger.addHandler(cls._run_file_handler)

        cls._current_run_id = run_id
        cls._loggers["scheduler"].info(f"开始新的运行: {run_id}")

    @classmethod
    def cleanup_run_logging(cls) -> None:
        """清理运行日志处理器"""
        if cls._run_file_handler:
            for logger in cls._loggers.values():
                if cls._run_file_handler in logger.handlers:
                    logger.removeHandler(cls._run_file_handler)
            cls._run_file_handler.close()
            cls._run_file_handler = None

            if cls._current_run_id:
                cls._loggers["scheduler"].info(f"结束运行: {cls._current_run_id}")
            cls._current_run_id = None


# 为了保持向后兼容，保留原来的setup_logger函数
setup_logger = LogManager.setup_logger
