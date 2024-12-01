import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from . import config

def setup_logger(name: Optional[str] = None,
                log_file: Optional[Union[str, Path]] = None,
                log_level: Optional[str] = None) -> logging.Logger:
    """设置日志记录器
    
    Args:
        name: 日志记录器名称，默认使用模块名
        log_file: 日志文件路径，默认使用config.LOG_FILE
        log_level: 日志级别，默认使用config.LOG_LEVEL
        
    Returns:
        配置好的日志记录器
    """
    # 配置日志记录器
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, log_level or config.LOG_LEVEL))
    
    if not logger.handlers:  # 避免重复添加处理器
        # 创建文件处理器
        log_file = log_file or config.LOG_FILE
        if isinstance(log_file, str):
            log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level or config.LOG_LEVEL))
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level or config.LOG_LEVEL))
        
        # 创建格式化器
        formatter = logging.Formatter(config.LOG_FORMAT)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到日志记录器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger
