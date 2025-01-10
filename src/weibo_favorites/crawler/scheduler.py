"""调度器模块，用于定时调度爬虫任务"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from .. import config
from ..database import save_weibo
from ..utils import LogManager
from .auth import CookieManager
from .crawler import crawl_favorites
from .queue import ImageProcessQueue, LongTextProcessQueue
from .run_history import RunLogger

# 设置日志记录器
logger = LogManager.setup_logger("scheduler")
loggers = LogManager.setup_module_loggers()


class Scheduler:
    """调度器类"""

    def __init__(self):
        """初始化调度器"""
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.next_run_time: Optional[datetime] = None
        self.run_interval = config.CRAWL_INTERVAL
        self.run_logger = RunLogger()
        self.last_update_time: Optional[datetime] = None

        # 进程间通信文件
        self.pid_file = config.SCHEDULER_PID_FILE
        self.status_file = config.SCHEDULER_STATUS_FILE

        # 初始化队列管理器
        self.ltp_queue = LongTextProcessQueue()
        self.img_queue = ImageProcessQueue()

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

    def start(self, cookie_manager: CookieManager):
        """启动调度器"""
        if self.is_running():
            logger.warning("调度器已在运行中")
            return False

        # 保存PID
        with open(self.pid_file, "w") as f:
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

                # 验证cookie有效性
                valid, error = cookie_manager.check_validity()
                if not valid:
                    logger.error(f"Cookie无效: {error}")
                    self.run_logger.update_run(
                        run_id,
                        status="error",
                        error="Cookie无效",
                        end_time=datetime.now().isoformat(),
                    )
                else:
                    # 创建session
                    session = cookie_manager.create_session()

                    # 开始执行任务
                    logger.info("开始执行爬取任务")
                    favorites = crawl_favorites(self.ltp_queue, self.img_queue, session)

                    # 更新运行记录
                    if favorites:
                        logger.info(f"任务完成，成功爬取并保存 {len(favorites)} 条收藏")
                        self.run_logger.update_run(
                            run_id,
                            status="success",
                            items_count=len(favorites),
                            end_time=datetime.now().isoformat(),
                        )
                    else:
                        logger.warning("任务完成，但未获取到数据")
                        self.run_logger.update_run(
                            run_id,
                            status="warning",
                            items_count=0,
                            end_time=datetime.now().isoformat(),
                        )

                # 计算耗时
                duration = time.time() - start_time
                logger.info(f"本次任务耗时: {duration:.2f} 秒")

                # 更新下次执行时间并等待
                self.next_run_time = datetime.now() + timedelta(
                    seconds=self.run_interval
                )
                self._update_status()

                wait_time = self.run_interval - duration
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
                    end_time=datetime.now().isoformat(),
                )
                time.sleep(self.run_interval)

            finally:
                LogManager.cleanup_run_logging()

        self._cleanup_files()
        return True

    def stop(self):
        """停止调度器"""
        if not self.is_running():
            return False
        
        # # 获取队列最终状态
        # final_status = {
        #     "long_text_queue": self.ltp_queue.get_queue_status(),
        #     "image_queue": self.img_queue.get_queue_status(),
        #     "stopped_at": datetime.now().isoformat()
        # }
        # logger.info("队列最终状态: %s", final_status)

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

    def check_queue_status(self):
        """检查队列状态"""
        # 检查长文本处理队列状态
        ltp_status = self.ltp_queue.get_queue_status()
        logger.info("长文本处理队列状态: %s", ltp_status)

        # 检查图片处理队列状态
        img_status = self.img_queue.get_queue_status()
        logger.info("图片处理队列状态: %s", img_status)

        # 如果两个队列都没有活跃的worker，可能需要报警
        if ltp_status["active_workers"] == 0 and img_status["active_workers"] == 0:
            logger.warning("没有活跃的worker，请检查队列状态")

        return {
            "long_text_queue": ltp_status,
            "image_queue": img_status,
            "last_checked": datetime.now().isoformat()
        }

    def cleanup_queues(self):
        """清理队列中的过期任务"""
        result = {
            "long_text_cleaned": 0,
            "image_cleaned": 0,
            "cleaned_at": datetime.now().isoformat(),
            "errors": []
        }

        try:
            # 清理长文本处理队列
            result["long_text_cleaned"] = self.ltp_queue.cleanup_jobs()
            logger.info("长文本处理队列清理完成，共清理 %d 个任务", result["long_text_cleaned"])
        except Exception as e:
            error_msg = f"长文本处理队列清理失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        try:
            # 清理图片处理队列
            result["image_cleaned"] = self.img_queue.cleanup_jobs()
            logger.info("图片处理队列清理完成，共清理 %d 个任务", result["image_cleaned"])
        except Exception as e:
            error_msg = f"图片处理队列清理失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    def retry_failed_jobs(self):
        """重试失败的任务"""
        result = {
            "long_text_retried": 0,
            "image_retried": 0,
            "retried_at": datetime.now().isoformat(),
            "errors": []
        }

        try:
            # 重试长文本处理队列中的失败任务
            result["long_text_retried"] = self.ltp_queue.retry_failed_jobs()
            logger.info("长文本处理队列重试完成，共重试 %d 个任务", result["long_text_retried"])
        except Exception as e:
            error_msg = f"长文本处理队列重试失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        try:
            # 重试图片处理队列中的失败任务
            result["image_retried"] = self.img_queue.retry_failed_jobs()
            logger.info("图片处理队列重试完成，共重试 %d 个任务", result["image_retried"])
        except Exception as e:
            error_msg = f"图片处理队列重试失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    def get_status(self):
        """获取调度器状态"""
        if not self.is_running() or not self.status_file.exists():
            return {
                "running": False,
                "current_time": datetime.now().isoformat(),
                "next_run": None,
                "interval": self.run_interval,
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
                "interval": self.run_interval,
            }

    def _update_status(self):
        """更新调度器状态文件"""
        status = {
            "running": self.running,
            "current_time": datetime.now().isoformat(),
            "next_run": self.next_run_time.isoformat() if self.next_run_time else None,
            "interval": self.run_interval,
        }

        try:
            with open(self.status_file, "w") as f:
                json.dump(status, f)
        except Exception as e:
            logger.error(f"更新状态文件失败: {e}")

    def _cleanup_queue(self):
        """内部方法：清理并重试队列任务
        
        此方法被废弃，请使用 cleanup_queues() 和 retry_failed_jobs() 方法替代
        """
        logger.warning("_cleanup_queue 方法已废弃，请使用 cleanup_queues() 和 retry_failed_jobs() 方法替代")
        cleanup_result = self.cleanup_queues()
        retry_result = self.retry_failed_jobs()
        return cleanup_result, retry_result

    def _cleanup_files(self):
        """清理状态文件"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
            if self.status_file.exists():
                self.status_file.unlink()
        except Exception as e:
            logger.error(f"清理状态文件失败: {e}")


def main():
    """主函数"""
    scheduler = Scheduler()
    cookie_manager = CookieManager()

    if scheduler.is_running():
        print("调度器已在运行中")
        return

    try:
        scheduler.start(cookie_manager)
    except KeyboardInterrupt:
        logger.info("收到终止信号，调度器停止运行")
    except Exception as e:
        logger.error(f"调度器异常退出: {e}")
        raise


if __name__ == "__main__":
    main()
