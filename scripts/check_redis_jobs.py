import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from redis import Redis
from rq import Queue
from rq.job import Job

from src.weibo_favorites import config

# 连接到 Redis
redis_conn = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB
)

# 检查所有队列
queues = {
    'failed': Queue('failed', connection=redis_conn),
    'image': Queue(config.IMAGE_CONTENT_PROCESS_QUEUE, connection=redis_conn),
    'long_text': Queue(config.LONG_TEXT_CONTENT_PROCESS_QUEUE, connection=redis_conn)
}

for queue_name, queue in queues.items():
    print(f"\n=== {queue_name} 队列 ===")
    print(f"队列长度: {len(queue)}")
    job_ids = queue.failed_job_registry.get_job_ids()
    if job_ids:
        jobs = Job.fetch_many(job_ids, connection=redis_conn)
        for job in jobs:
            print(f"\nJob ID: {job.id}")
            print(f"状态: {job.get_status()}")
            print(f"函数: {job.func_name}")
            print(f"参数: {job.args}")
            if job.exc_info:
                print(f"异常信息: {job.exc_info}")
    else:
        print("队列为空")
