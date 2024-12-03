#!/usr/bin/env python3
"""定时任务调度器

自动执行微博收藏爬取任务，支持：
1. 定时执行爬取任务
2. 检查 cookies 状态
3. 错误重试
4. 独立的日志记录
"""

import time
import logging
from datetime import datetime
from pathlib import Path

from . import config
from .auth import load_cookies
from .crawler import crawl_favorites
from .database import save_weibo
from .utils import setup_logger

# 设置调度器日志
scheduler_logger = setup_logger(
    "scheduler",
)

def check_cookies() -> bool:
    """检查 cookies 是否可用
    
    Returns:
        bool: cookies 是否可用
    """
    try:
        cookies = load_cookies()
        return bool(cookies)
    except Exception as e:
        scheduler_logger.error(f"加载 cookies 失败: {e}")
        return False

def run_task():
    """执行单次爬取任务"""
    try:
        # 检查 cookies
        if not check_cookies():
            scheduler_logger.error("cookies 不可用，请先手动登录")
            return False
            
        # 加载 cookies
        cookies = load_cookies()
        
        # 执行爬取
        scheduler_logger.info("开始执行爬取任务")
        favorites = crawl_favorites(cookies)
        
        # 检查结果
        if favorites:
            # 保存到数据库
            try:
                save_weibo(favorites)
                scheduler_logger.info(f"成功保存 {len(favorites)} 条收藏到数据库")
            except Exception as e:
                scheduler_logger.error(f"保存到数据库失败: {e}")
                return False
                
            scheduler_logger.info(f"任务完成，成功爬取并保存 {len(favorites)} 条收藏")
            return True
        else:
            scheduler_logger.warning("任务完成，但未获取到数据")
            return True
            
    except Exception as e:
        scheduler_logger.error(f"任务执行失败: {e}")
        return False

def run_scheduler():
    """运行调度器"""
    scheduler_logger.info("启动调度器")
    
    while True:
        start_time = datetime.now()
        scheduler_logger.info(f"开始新的任务周期: {start_time}")
        
        # 执行任务
        success = False
        retries = 0
        
        while not success and retries < config.MAX_RETRIES:
            if retries > 0:
                scheduler_logger.info(f"第 {retries} 次重试")
                time.sleep(config.RETRY_DELAY)
                
            success = run_task()
            retries += 1
            
        if not success:
            scheduler_logger.error(f"任务执行失败，已重试 {retries} 次")
        
        # 计算下次执行时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        sleep_time = max(0, config.CRAWL_INTERVAL - duration)
        
        scheduler_logger.info(f"本次任务耗时: {duration:.2f} 秒")
        scheduler_logger.info(f"等待 {sleep_time:.2f} 秒后执行下一次任务")
        
        time.sleep(sleep_time)

def main():
    """主函数"""
    try:
        run_scheduler()
    except KeyboardInterrupt:
        scheduler_logger.info("收到终止信号，调度器停止运行")
    except Exception as e:
        scheduler_logger.error(f"调度器异常退出: {e}")
        raise

if __name__ == "__main__":
    main()
