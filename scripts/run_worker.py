"""
启动队列工作进程
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from weibo_favorites.crawler.queue_worker import QueueWorker

if __name__ == '__main__':
    worker = QueueWorker()
    worker.run()
