"""数据库操作模块"""

import sqlite3
from typing import Any, Dict, List
from contextlib import contextmanager

from . import config
from .utils import LogManager

logger = LogManager.setup_logger("database")


@contextmanager
def get_connection() -> sqlite3.Connection:
    """获取数据库连接，支持加载SQLite扩展

    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    conn = None
    try:
        # 连接数据库，设置超时和隔离级别
        conn = sqlite3.connect(
            config.settings.DATABASE_FILE,
            timeout=20.0,  # 设置更长的超时时间
            isolation_level=None,  # 自动提交模式
        )
        conn.execute("PRAGMA journal_mode=WAL")  # 使用 WAL 模式提高并发性能
        
        # 加载SQLite扩展
        conn.enable_load_extension(True)
        conn.load_extension(config.EXTENSION_SIMPLE_PATH)
        
        yield conn
        
    finally:
        if conn:
            conn.close()


def create_table():
    """创建数据库表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 创建微博表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS weibo_favorites (
                id TEXT PRIMARY KEY,
                mblogid TEXT,
                created_at TEXT,
                url TEXT,
                user_name TEXT,
                user_id TEXT,
                is_long_text INTEGER,
                text TEXT,
                text_html TEXT,
                long_text TEXT,
                source TEXT,
                links TEXT,
                collected_at TEXT,
                text_length INTEGER,
                crawled INTEGER DEFAULT 0,
                crawl_status TEXT DEFAULT 'pending',
                updated_at TEXT
            )"""
        )
        
        # 创建图片表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS weibo_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weibo_id TEXT NOT NULL,
                pic_id TEXT NOT NULL,
                url TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                content_type TEXT,
                raw_content BLOB,
                thumbnail BLOB,
                compressed BLOB,
                created_at TEXT,
                processed INTEGER DEFAULT 0,
                process_status TEXT DEFAULT 'pending',
                UNIQUE(weibo_id, pic_id)
            )"""
        )
        
        conn.commit()


def save_weibo(weibo: Dict[str, Any]):
    """保存单条微博数据"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO weibo_favorites (
                id, mblogid, created_at, url, user_name, user_id, is_long_text, text, text_html,
                long_text, source, links, collected_at, text_length, crawled, crawl_status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                weibo["id"],
                weibo["mblogid"],
                weibo["created_at"],
                weibo["url"],
                weibo["user_name"],
                weibo["user_id"],
                weibo["is_long_text"],
                weibo["text"],
                weibo["text_html"],
                weibo["long_text"],
                weibo["source"],
                ",".join(weibo["links"]),
                weibo["collected_at"],
                len(weibo["text"]),
                weibo.get("crawled", False),
                weibo.get(
                    "crawl_status",
                    "completed" if not weibo["is_long_text"] else "pending",
                ),
                weibo.get("updated_at"),
            ),
        )
        conn.commit()
def update_weibo_content(weibo_id: str, update_data: Dict[str, Any]):
    """更新微博内容

    Args:
        weibo_id: 微博ID
        update_data: 要更新的数据字段
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # 构建更新语句
        update_fields = []
        values = []
        for key, value in update_data.items():
            if key in [
                "long_text",
                "text_length",
                "crawled",
                "crawl_status",
                "updated_at",
            ]:
                update_fields.append(f"{key} = ?")
                values.append(value)

        if not update_fields:
            return

        values.append(weibo_id)  # WHERE 条件的值

        sql = f"""
            UPDATE weibo_favorites
            SET {', '.join(update_fields)}
            WHERE id = ?
        """

        cursor.execute(sql, values)
        conn.commit()

def save_image_metadata(image_data: Dict[str, Any]):
    """保存图片元数据

    Args:
        image_data: 图片数据，包含以下字段：
            - weibo_id: 微博ID
            - pic_id: 图片ID
            - url: 图片URL
            - width: 图片宽度
            - height: 图片高度
            - content_type: 图片类型
            - content: 图片二进制数据
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO weibo_images (
                weibo_id, pic_id, url, width, height, content_type, raw_content,
                created_at, processed, process_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 0, 'pending')
            """,
            (
                image_data["weibo_id"],
                image_data["pic_id"],
                image_data["url"],
                image_data.get("width"),
                image_data.get("height"),
                image_data["content_type"],
                image_data["content"]
            )
        )
        conn.commit()


def update_image_process_result(weibo_id: str, pic_id: str, processed_images: Dict[str, bytes]):
    """更新图片处理结果

    Args:
        weibo_id: 微博ID
        pic_id: 图片ID
        processed_images: 处理后的图片数据，包含以下字段：
            - thumbnail: 缩略图数据
            - compressed: 压缩后的图片数据
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE weibo_images
            SET processed = 1,
                process_status = 'success',
                thumbnail = ?,
                compressed = ?
            WHERE weibo_id = ? AND pic_id = ?
            """,
            (
                processed_images["thumbnail"],
                processed_images["compressed"],
                weibo_id,
                pic_id
            )
        )
        conn.commit()


def update_image_process_status(weibo_id: str, pic_id: str, error_msg: str):
    """更新图片处理状态

    Args:
        weibo_id: 微博ID
        pic_id: 图片ID
        error_msg: 错误信息
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE weibo_images
            SET process_status = ?
            WHERE weibo_id = ? AND pic_id = ?
            """,
            (
                f"error: {error_msg}",
                weibo_id,
                pic_id
            )
        )
        conn.commit()

def get_pending_long_text_weibos() -> List[Dict[str, Any]]:
    """获取待处理的长文本微博列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, mblogid, is_long_text, crawl_status
            FROM weibo_favorites
            WHERE is_long_text = 1 AND crawl_status = 'pending'
            ORDER BY created_at DESC
        """
        )

        columns = ["id", "mblogid", "is_long_text", "crawl_status"]

        return [dict(zip(columns, row)) for row in cursor.fetchall()]
