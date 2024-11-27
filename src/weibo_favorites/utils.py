import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """设置日志记录器
    
    Args:
        name: 日志记录器名称，默认使用模块名
        
    Returns:
        配置好的日志记录器
    """
    # 配置日志记录器
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    if not logger.handlers:  # 避免重复添加处理器
        # 创建文件处理器
        file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        
        # 创建格式化器
        formatter = logging.Formatter(config.LOG_FORMAT)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到日志记录器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger
