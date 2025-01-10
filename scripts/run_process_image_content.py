import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from weibo_favorites.crawler.tasks import process_image_content

if __name__ == '__main__':
    task_data = {
        'weibo_id': '5119369850654791',
        'pic_id': '5396ee05ly1hx9kh3kqo9j22a42q84qq',
        'url': 'https://wx1.sinaimg.cn/mw2000/5396ee05ly1hx9kh3kqo9j22a42q84qq.jpg',
        'width': 2000,
        'height': 2392
    }
    result = process_image_content(task_data)
    print(result)