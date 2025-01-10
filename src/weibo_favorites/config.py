"""Configuration module for the Weibo Favorites Crawler."""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directory
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
RUNS_DIR = LOGS_DIR / "runs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# File paths
COOKIES_FILE = DATA_DIR / "weibo_cookies.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"
DATABASE_FILE = DATA_DIR / "weibo_favorites.db"
CRAWLER_STATE_FILE = DATA_DIR / "crawler_state.json"  # 新增：爬虫状态文件
HISTORY_FILE = LOGS_DIR / "history.json"  # 新增：爬虫历史记录文件
SCHEDULER_PID_FILE = DATA_DIR / "scheduler.pid"
SCHEDULER_STATUS_FILE = DATA_DIR / "scheduler_status.json"

# Weibo API configuration
BASE_URL = "https://weibo.com/ajax/favorites/all_fav"
LONG_TEXT_CONTENT_URL = "https://weibo.com/ajax/statuses/longtext?id="
REQUEST_DELAY = 2  # seconds between requests

# Logging configuration
LOG_FILE = LOGS_DIR / "app.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# Scheduler configuration
CRAWL_INTERVAL = 3600  # 爬取间隔（秒）
MAX_RETRIES = 1  # 最大重试次数
RETRY_DELAY = 30  # 重试间隔（秒）

# Redis configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Queue configuration
LONG_TEXT_CONTENT_PROCESS_QUEUE = "long_text_content_process"
IMAGE_PROCESS_QUEUE = "image_content_process"  # 新增：图片处理队列名称
MAX_RETRY_COUNT = 3  # 最大重试次数
RETRY_DELAY = 300  # 重试延迟（秒）
QUEUE_CLEANUP_INTERVAL = 86400  # 队列清理间隔（秒）
FAILED_JOBS_RETENTION = 604800  # 失败任务保留时间（秒）
FINISHED_JOBS_RETENTION = 86400  # 完成任务保留时间（秒）

# Rate limiting configuration
RATE_LIMIT_ENABLED = True  # 是否启用速率限制
RATE_LIMIT_WINDOW = 60  # 速率限制窗口（秒）
LONG_TEXT_RATE_LIMIT = 20  # 长文本处理的每分钟最大请求数
IMAGE_RATE_LIMIT = 10  # 图片处理的每分钟最大请求数
