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
from .run_history import RunLogger
from .utils import LogManager

"""调度器模块"""
# 设置所有模块的日志记录器
loggers = LogManager.setup_module_loggers()
logger = loggers['scheduler']

class Scheduler:
    def __init__(self):
        self.interval = config.CRAWL_INTERVAL
        self.running = False
        self.run_logger = RunLogger()
    
    def start(self):
        """启动调度器"""
        self.running = True
        logger.info("启动调度器")
        
        while self.running:
            start_time = time.time()
            run_id = self.run_logger.start_new_run()
            LogManager.setup_run_logging(run_id)
            
            try:
                logger.info(f"开始新的任务周期: {datetime.now().isoformat()}")
                
                # 检查 cookies
                if not self.check_cookies():
                    logger.error("cookies 不可用，请先手动登录")
                    self.run_logger.update_run(
                        run_id,
                        status="error",
                        error="cookies 不可用",
                        end_time=datetime.now().isoformat()
                    )
                    continue
                
                # 加载 cookies
                cookies = load_cookies()
                logger.info("成功加载 cookies")
                
                # 开始执行任务
                logger.info("开始执行爬取任务")
                favorites = crawl_favorites(cookies)
                
                if favorites:
                    # 保存到数据库
                    save_weibo(favorites)
                    logger.info(f"成功保存 {len(favorites)} 条收藏到数据库")
                    logger.info(f"任务完成，成功爬取并保存 {len(favorites)} 条收藏")
                    
                    # 更新运行记录
                    self.run_logger.update_run(
                        run_id,
                        status="success",
                        items_count=len(favorites),
                        end_time=datetime.now().isoformat()
                    )
                else:
                    logger.warning("任务完成，但未获取到数据")
                    self.run_logger.update_run(
                        run_id,
                        status="warning",
                        items_count=0,
                        end_time=datetime.now().isoformat()
                    )
                
                duration = time.time() - start_time
                logger.info(f"本次任务耗时: {duration:.2f} 秒")
                
                # 等待下一次执行
                wait_time = self.interval - duration
                if wait_time > 0:
                    logger.info(f"等待 {wait_time:.2f} 秒后执行下一次任务")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"任务执行失败: {str(e)}")
                self.run_logger.update_run(
                    run_id,
                    status="error",
                    error=str(e),
                    end_time=datetime.now().isoformat()
                )
                time.sleep(config.RETRY_DELAY)
            finally:
                LogManager.cleanup_run_logging()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        logger.info("收到终止信号，调度器停止运行")
        LogManager.cleanup_run_logging()
    
    def check_cookies(self) -> bool:
        """检查 cookies 是否可用
        
        Returns:
            bool: cookies 是否可用
        """
        try:
            cookies = load_cookies()
            return bool(cookies)
        except Exception as e:
            logger.error(f"加载 cookies 失败: {e}")
            return False

def main():
    """主函数"""
    try:
        scheduler = Scheduler()
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("收到终止信号，调度器停止运行")
    except Exception as e:
        logger.error(f"调度器异常退出: {e}")
        raise

if __name__ == "__main__":
    main()
