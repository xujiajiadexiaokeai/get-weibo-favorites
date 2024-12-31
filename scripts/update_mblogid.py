# update_mblogid.py

import logging
import sqlite3

from weibo_favorites import config

# 日志配置
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 数据库文件路径
db_path = config.DATABASE_FILE

# 打开数据库连接
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询包含 URL 的数据
cursor.execute("SELECT id, url FROM weibo_favorites WHERE url != '' AND mblogid IS NULL")
rows = cursor.fetchall()

# 处理每一行数据并提取 id 字段
update_data = []
for row in rows:
    record_id, url = row
    if url:
        # 提取最后一个 '/' 后面的部分
        mblogid = url.split("/")[-1]
        update_data.append((mblogid, record_id))

logging.info(f"update_data_len: {len(update_data)}")

# 更新 mblogid 列
if update_data:
    cursor.executemany(
        "UPDATE weibo_favorites SET mblogid = ? WHERE id = ?", update_data
    )
    conn.commit()

# 关闭数据库连接
conn.close()

print("数据库更新完成！")
