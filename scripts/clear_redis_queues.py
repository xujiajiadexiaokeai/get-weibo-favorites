from redis import Redis
from rq import Queue

from src.weibo_favorites import config

# 连接到 Redis
redis_conn = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB
)

# 清空所有队列
queues = {
    'image_process': Queue(config.IMAGE_CONTENT_PROCESS_QUEUE, connection=redis_conn),
    'long_text_content_process': Queue(config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=redis_conn)
}

for queue_name, queue in queues.items():
    print(f"正在清空 {queue_name} 队列...")
    queue.empty()
    print(f"{queue_name} 队列已清空")
