"""调度器模块"""
import os
import json
import time
from datetime import datetime, timedelta

from .. import config
from .auth import load_cookies
from .crawler import crawl_favorites
from ..database import save_weibo
from .run_history import RunLogger
from ..utils import LogManager
from .queue_manager import LongTextQueue

# 设置日志记录器
logger = LogManager.setup_logger('scheduler')
loggers = LogManager.setup_module_loggers()

class Scheduler:
    def __init__(self):
        self.interval = config.CRAWL_INTERVAL
        self.running = False
        self.run_logger = RunLogger()
        self.next_run_time = None
        
        # 进程间通信文件
        self.pid_file = config.SCHEDULER_PID_FILE
        self.status_file = config.SCHEDULER_STATUS_FILE
        
        # 初始化队列管理器
        self.queue_manager = LongTextQueue()
    
    def is_running(self):
        """检查调度器是否在运行"""
        if not self.pid_file.exists():
            return False
            
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            
            # 获取进程信息
            os.kill(pid, 0)
            return True
            
        except (FileNotFoundError, ProcessLookupError, ValueError):
            self._cleanup_files()
            return False
    
    def start(self):
        """启动调度器"""
        if self.is_running():
            logger.warning("调度器已在运行中")
            return False
            
        # 保存PID
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        self.running = True
        logger.info("启动调度器")
        self._update_status()
        
        last_cleanup_time = time.time()
        
        while self.running:
            start_time = time.time()
            run_id = self.run_logger.start_new_run()
            LogManager.setup_run_logging(run_id)
            
            try:
                logger.info(f"开始新的任务周期: {datetime.now().isoformat()}")
                
                # 检查是否需要清理队列
                if time.time() - last_cleanup_time >= config.QUEUE_CLEANUP_INTERVAL:
                    self._cleanup_queue()
                    last_cleanup_time = time.time()
                
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
                favorites = crawl_favorites(cookies, self.queue_manager)
                
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
                
                # 计算耗时
                duration = time.time() - start_time
                logger.info(f"本次任务耗时: {duration:.2f} 秒")
                
                # 更新下次执行时间并等待
                self.next_run_time = datetime.now() + timedelta(seconds=self.interval)
                self._update_status()
                
                wait_time = self.interval - duration
                if wait_time > 0:
                    logger.info(f"等待 {wait_time:.2f} 秒后执行下一次任务")
                    time.sleep(wait_time)
                
            except KeyboardInterrupt:
                logger.info("收到终止信号")
                break
                
            except Exception as e:
                logger.exception("任务执行出错")
                self.run_logger.update_run(
                    run_id,
                    status="error",
                    error=str(e),
                    end_time=datetime.now().isoformat()
                )
                time.sleep(self.interval)
                
            finally:
                LogManager.cleanup_run_logging()
        
        self._cleanup_files()
        return True
    
    def stop(self):
        """停止调度器"""
        if not self.is_running():
            return False
            
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            logger.info(f"正在停止调度器进程 (PID: {pid})")
            os.kill(pid, 15)  # 发送SIGTERM信号
            
            # 等待进程结束并回收
            max_wait = 5  # 最多等待5秒
            start_time = time.time()
            while time.time() - start_time < max_wait:
                try:
                    # WNOHANG 表示如果子进程还没有退出就立即返回
                    # 返回值: (pid, status) 如果进程结束，0 如果进程还在运行
                    wpid, status = os.waitpid(pid, os.WNOHANG)
                    if wpid == pid:  # 进程已经结束
                        exit_code = status >> 8  # 获取退出码
                        logger.info(f"调度器进程已停止 (退出码: {exit_code})")
                        self._cleanup_files()
                        return True
                except ChildProcessError:  # 不是当前进程的子进程
                    try:
                        os.kill(pid, 0)  # 检查进程是否还在运行
                        time.sleep(0.5)
                    except ProcessLookupError:  # 进程已经不存在
                        logger.info("调度器进程已停止")
                        self._cleanup_files()
                        return True
                time.sleep(0.5)
            
            logger.warning(f"调度器进程在 {max_wait} 秒内未能正常停止")
            return True
            
        except (FileNotFoundError, ValueError):
            self._cleanup_files()
            return False
        except ProcessLookupError:
            logger.info("调度器进程已停止")
            self._cleanup_files()
            return True
    
    def get_status(self):
        """获取调度器状态"""
        if not self.is_running() or not self.status_file.exists():
            return {
                "running": False,
                "current_time": datetime.now().isoformat(),
                "next_run": None,
                "interval": self.interval
            }
            
        try:
            with open(self.status_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取状态文件失败: {e}")
            return {
                "error": "无法读取调度器状态",
                "running": False,
                "current_time": datetime.now().isoformat(),
                "next_run": None,
                "interval": self.interval
            }
    
    def _update_status(self):
        """更新调度器状态文件"""
        status = {
            "running": self.running,
            "current_time": datetime.now().isoformat(),
            "next_run": self.next_run_time.isoformat() if self.next_run_time else None,
            "interval": self.interval
        }
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            logger.error(f"更新状态文件失败: {e}")
    
    def _cleanup_queue(self):
        """清理队列中的过期任务"""
        try:
            cleanup_result = self.queue_manager.cleanup_jobs()
            logger.info(f"队列清理完成: {cleanup_result}")
            
            # 重试失败的任务
            retry_count = self.queue_manager.retry_failed_jobs()
            if retry_count > 0:
                logger.info(f"重试了 {retry_count} 个失败任务")
        except Exception as e:
            logger.error(f"队列清理失败: {e}")
    
    def _cleanup_files(self):
        """清理状态文件"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
            if self.status_file.exists():
                self.status_file.unlink()
        except Exception as e:
            logger.error(f"清理状态文件失败: {e}")
    
    def check_cookies(self) -> bool:
        """检查 cookies 是否可用"""
        cookies_file = config.COOKIES_FILE
        return cookies_file.exists()

def main():
    """主函数"""
    scheduler = Scheduler()
    
    if scheduler.is_running():
        print("调度器已在运行中")
        return
        
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("收到终止信号，调度器停止运行")
    except Exception as e:
        logger.error(f"调度器异常退出: {e}")
        raise

if __name__ == "__main__":
    main()
