"""Configuration module for the Weibo Favorites Crawler."""

import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directory
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# File paths
COOKIES_FILE = DATA_DIR / "weibo_cookies.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"
DATABASE_FILE = DATA_DIR / "weibo_favorites.db"

# Weibo API configuration
BASE_URL = "https://weibo.com/ajax/favorites/all_fav"
REQUEST_DELAY = 2  # seconds between requests

# Logging configuration
LOG_FILE = LOGS_DIR / "weibo_favorites.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
