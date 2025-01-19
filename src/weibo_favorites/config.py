"""Configuration module for the Weibo Favorites Crawler."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, computed_field

class Settings(BaseSettings):
    # Project root directory
    PROJECT_ROOT: Path = Field(default=Path(__file__).parent.parent.parent, description="项目根目录")
    
    # Test mode settings
    _test_mode: bool = False
    _test_db_path: Optional[Path] = None

    @computed_field(description="数据目录")
    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data"

    @computed_field(description="日志目录")
    @property
    def LOGS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "logs"

    @computed_field(description="运行日志目录")
    @property
    def RUNS_DIR(self) -> Path:
        return self.LOGS_DIR / "runs"

    # File paths
    @computed_field(description="Cookies文件")
    @property
    def COOKIES_FILE(self) -> str:
        return str(self.DATA_DIR / "weibo_cookies.json")

    @computed_field(description="收藏文件")
    @property
    def FAVORITES_FILE(self) -> str:
        return str(self.DATA_DIR / "favorites.json")

    @computed_field(description="数据库文件")
    @property
    def DATABASE_FILE(self) -> str:
        if self._test_mode and self._test_db_path:
            return str(self._test_db_path)
        return str(self.DATA_DIR / "weibo_favorites.db")

    @computed_field(description="爬虫状态文件")
    @property
    def CRAWLER_STATE_FILE(self) -> str:
        return str(self.DATA_DIR / "crawler_state.json")

    @computed_field(description="爬虫历史记录文件")
    @property
    def HISTORY_FILE(self) -> str:
        return str(self.LOGS_DIR / "history.json")

    @computed_field(description="调度器PID文件")
    @property
    def SCHEDULER_PID_FILE(self) -> str:
        return str(self.DATA_DIR / "scheduler.pid")

    @computed_field(description="调度器状态文件")
    @property
    def SCHEDULER_STATUS_FILE(self) -> str:
        return str(self.DATA_DIR / "scheduler_status.json")

    # Weibo API configuration
    BASE_URL: str = Field(default="https://weibo.com/ajax/favorites/all_fav", description="微博API基础URL")
    LONG_TEXT_CONTENT_URL: str = Field(default="https://weibo.com/ajax/statuses/longtext?id=", description="长文本内容URL")
    REQUEST_DELAY: int = Field(default=2, description="请求延迟（秒）")

    # Weibo configuration
    WEIBO_UID: str = Field(default="", description="微博用户ID")

    # Logging configuration
    @computed_field(description="日志文件")
    @property
    def LOG_FILE(self) -> str:
        return str(self.LOGS_DIR / "app.log")

    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")

    # Scheduler configuration
    CRAWL_INTERVAL: int = Field(default=3600, description="爬取间隔（秒）")
    MAX_RETRIES: int = Field(default=1, description="最大重试次数")
    RETRY_DELAY: int = Field(default=30, description="重试间隔（秒）")

    # Redis configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis服务器地址")
    REDIS_PORT: int = Field(default=6379, description="Redis服务器端口")
    REDIS_DB: int = Field(default=0, description="Redis数据库编号")

    # Queue configuration
    LONG_TEXT_CONTENT_PROCESS_QUEUE: str = Field(default="long_text_content_process", description="长文本内容处理队列")
    IMAGE_CONTENT_PROCESS_QUEUE: str = Field(default="image_content_process", description="图片内容处理队列")
    MAX_RETRY_COUNT: int = Field(default=3, description="最大重试次数")
    RETRY_DELAY: int = Field(default=300, description="重试延迟（秒）")
    QUEUE_CLEANUP_INTERVAL: int = Field(default=86400, description="队列清理间隔（秒）")
    FAILED_JOBS_RETENTION: int = Field(default=604800, description="失败任务保留时间（秒）")
    FINISHED_JOBS_RETENTION: int = Field(default=86400, description="完成任务保留时间（秒）")

    # Rate limiting configuration
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="是否启用速率限制")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="速率限制窗口（秒）")
    LONG_TEXT_RATE_LIMIT: int = Field(default=20, description="长文本处理的每分钟最大请求数")
    IMAGE_RATE_LIMIT: int = Field(default=10, description="图片处理的每分钟最大请求数")

    # Extension configuration
    EXTENSION_SIMPLE_PATH: str = Field(default="libs/libsimple", description="扩展模块路径")

    def enable_test_mode(self, db_path: Optional[Path] = None) -> None:
        """启用测试模式，可以指定测试用的数据库文件路径

        Args:
            db_path: 测试数据库文件路径
        """
        self._test_mode = True
        self._test_db_path = db_path

    def disable_test_mode(self) -> None:
        """禁用测试模式，恢复使用默认配置"""
        self._test_mode = False
        self._test_db_path = None

    class ConfigDict:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()

# 导出配置变量，保持向后兼容
PROJECT_ROOT = settings.PROJECT_ROOT
DATA_DIR = settings.DATA_DIR
LOGS_DIR = settings.LOGS_DIR
RUNS_DIR = settings.RUNS_DIR
COOKIES_FILE = settings.COOKIES_FILE
FAVORITES_FILE = settings.FAVORITES_FILE
DATABASE_FILE = settings.DATABASE_FILE
CRAWLER_STATE_FILE = settings.CRAWLER_STATE_FILE
HISTORY_FILE = settings.HISTORY_FILE
SCHEDULER_PID_FILE = settings.SCHEDULER_PID_FILE
SCHEDULER_STATUS_FILE = settings.SCHEDULER_STATUS_FILE
BASE_URL = settings.BASE_URL
LONG_TEXT_CONTENT_URL = settings.LONG_TEXT_CONTENT_URL
REQUEST_DELAY = settings.REQUEST_DELAY
WEIBO_UID = settings.WEIBO_UID
LOG_FILE = settings.LOG_FILE
LOG_FORMAT = settings.LOG_FORMAT
LOG_LEVEL = settings.LOG_LEVEL
CRAWL_INTERVAL = settings.CRAWL_INTERVAL
MAX_RETRIES = settings.MAX_RETRIES
RETRY_DELAY = settings.RETRY_DELAY
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
REDIS_DB = settings.REDIS_DB
LONG_TEXT_CONTENT_PROCESS_QUEUE = settings.LONG_TEXT_CONTENT_PROCESS_QUEUE
IMAGE_CONTENT_PROCESS_QUEUE = settings.IMAGE_CONTENT_PROCESS_QUEUE
MAX_RETRY_COUNT = settings.MAX_RETRY_COUNT
RETRY_DELAY = settings.RETRY_DELAY
QUEUE_CLEANUP_INTERVAL = settings.QUEUE_CLEANUP_INTERVAL
FAILED_JOBS_RETENTION = settings.FAILED_JOBS_RETENTION
FINISHED_JOBS_RETENTION = settings.FINISHED_JOBS_RETENTION
RATE_LIMIT_ENABLED = settings.RATE_LIMIT_ENABLED
RATE_LIMIT_WINDOW = settings.RATE_LIMIT_WINDOW
LONG_TEXT_RATE_LIMIT = settings.LONG_TEXT_RATE_LIMIT
IMAGE_RATE_LIMIT = settings.IMAGE_RATE_LIMIT
EXTENSION_SIMPLE_PATH = settings.EXTENSION_SIMPLE_PATH