import logging
import sys
from typing import Optional

# 设置日志
def setup_logger() -> logging.Logger:
    """设置日志记录器
    
    Returns:
        配置好的日志记录器
    """
    # 创建logs目录（如果不存在）
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # 生成日志文件名
    current_time = datetime.now()
    date_str = current_time.strftime("%Y%m%d")
    time_str = current_time.strftime("%H%M")
    log_filename = f"logs/logs-{date_str}-{time_str}.log"
    
    # 配置日志记录器
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
