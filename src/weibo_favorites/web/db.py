"""数据库操作模块"""

import sqlite3
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager

from .. import config
from ..utils import LogManager

logger = LogManager.setup_logger("web")


class WeiboDB:
    """微博数据库管理类"""
    
    def __init__(self, database_file: str = None, extension_path: str = None):
        """初始化数据库管理器
        
        Args:
            database_file: 数据库文件路径，默认使用配置文件中的路径
            extension_path: SQLite扩展路径，默认使用配置文件中的路径
        """
        self.database_file = database_file or config.DATABASE_FILE
        self.extension_path = extension_path or config.EXTENSION_SIMPLE_PATH
        self._init_fts()
    
    @staticmethod
    def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict:
        """将查询结果转换为字典格式"""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = self.dict_factory
        
        try:
            # 加载扩展
            conn.enable_load_extension(True)
            conn.load_extension(self.extension_path)
            yield conn
        finally:
            conn.close()
    
    def _init_fts(self):
        """初始化全文搜索"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 删除旧的FTS表（如果存在）并重新创建
            try:
                cursor.execute("DROP TABLE IF EXISTS weibo_fts")
                cursor.execute(
                    """
                    CREATE VIRTUAL TABLE weibo_fts USING fts5(
                        id UNINDEXED,  -- 不索引ID字段
                        text,          -- 索引短文本
                        long_text,     -- 索引长文本
                        user_name,     -- 索引用户名
                        created_at UNINDEXED,  -- 不索引时间
                        content='weibo_favorites',  -- 指定内容来源表
                        content_rowid='rowid',      -- 指定行ID
                        tokenize='simple'           -- 使用unicode分词器
                    )"""
                )
                
                # 创建触发器以保持FTS表同步
                cursor.executescript("""
                    -- 插入触发器
                    CREATE TRIGGER IF NOT EXISTS weibo_fts_insert AFTER INSERT ON weibo_favorites BEGIN
                        INSERT INTO weibo_fts(rowid, id, text, long_text, user_name, created_at)
                        VALUES (new.rowid, new.id, new.text, new.long_text, new.user_name, new.created_at);
                    END;

                    -- 删除触发器
                    CREATE TRIGGER IF NOT EXISTS weibo_fts_delete AFTER DELETE ON weibo_favorites BEGIN
                        INSERT INTO weibo_fts(weibo_fts, rowid, id, text, long_text, user_name, created_at)
                        VALUES('delete', old.rowid, old.id, old.text, old.long_text, old.user_name, old.created_at);
                    END;

                    -- 更新触发器
                    CREATE TRIGGER IF NOT EXISTS weibo_fts_update AFTER UPDATE ON weibo_favorites BEGIN
                        INSERT INTO weibo_fts(weibo_fts, rowid, id, text, long_text, user_name, created_at)
                        VALUES('delete', old.rowid, old.id, old.text, old.long_text, old.user_name, old.created_at);
                        INSERT INTO weibo_fts(rowid, id, text, long_text, user_name, created_at)
                        VALUES (new.rowid, new.id, new.text, new.long_text, new.user_name, new.created_at);
                    END;
                """)

                # 同步现有数据到FTS表
                cursor.execute("""
                    INSERT INTO weibo_fts(rowid, id, text, long_text, user_name, created_at)
                    SELECT rowid, id, text, long_text, user_name, created_at
                    FROM weibo_favorites
                """)
                
                cursor.execute("SELECT COUNT(*) as total FROM weibo_favorites")
                total = cursor.fetchone()["total"]
                logger.info(f"已同步 {total} 条数据到FTS表")
                
            except Exception as e:
                logger.error(f"初始化FTS表失败: {e}")
                return
            
            conn.commit()
    
    def _get_weibo_images(self, cursor: sqlite3.Cursor, weibo_id: str, use_thumbnail: bool = False) -> List[Dict]:
        """获取微博的图片信息
    
        Args:
            cursor: 数据库游标
            weibo_id: 微博ID
            use_thumbnail: 是否使用缩略图，True则返回thumbnail字段，False则返回raw_content字段
        """
        cursor.execute(
            """
            SELECT 
                pic_id,
                url,
                width,
                height,
                content_type,
                raw_content,
                thumbnail,
                process_status
            FROM weibo_images
            WHERE weibo_id = ? AND processed = 1
            ORDER BY id ASC
            """,
            (weibo_id,)
        )
        images = cursor.fetchall()
        
        # 处理图片数据
        for image in images:
            # 选择使用哪个图片数据
            img_data = image['thumbnail'] if use_thumbnail else image['raw_content']
            if img_data:
                # 转换为base64字符串
                b64_data = base64.b64encode(img_data).decode('utf-8')
                image['data_url'] = f"data:{image['content_type']};base64,{b64_data}"
            else:
                # 如果没有处理好的图片数据，使用原始URL
                image['data_url'] = image['url']
                
            # 清理不需要的字段
            del image['thumbnail']
            del image['raw_content']
            del image['url']
        
        return images
    
    def get_weibo_by_id(self, weibo_id: str) -> Optional[Dict]:
        """根据ID获取单条微博"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT * FROM weibo_favorites WHERE id = ?
                    """,
                    (weibo_id,)
                ).fetchone()
                
                if row:
                    row["images"] = self._get_weibo_images(cursor, weibo_id)
                
                return row
            except Exception as e:
                logger.error(f"获取微博详情失败: {e}")
                return None
    
    def get_favorites(self, page: int = 1, per_page: int = 20) -> tuple[List[Dict], int]:
        """获取收藏列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 计算总数
                total = cursor.execute(
                    "SELECT COUNT(*) as total FROM weibo_favorites"
                ).fetchone()["total"]
                
                # 获取分页数据
                offset = (page - 1) * per_page
                rows = cursor.execute(
                    """
                    SELECT * FROM weibo_favorites 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (per_page, offset)
                ).fetchall()
                
                # 获取每条微博的图片
                for row in rows:
                    row["images"] = self._get_weibo_images(cursor, row["id"], use_thumbnail=True)
                
                return rows, total
                
            except Exception as e:
                logger.error(f"获取收藏列表失败: {e}")
                return [], 0
    
    def search_weibos(self, query: str, page: int = 1, per_page: int = 20) -> tuple[List[Dict], int]:
        """搜索微博内容"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 计算总数
                total = cursor.execute(
                    """
                    SELECT COUNT(*) as total
                    FROM weibo_favorites 
                    JOIN weibo_fts ON weibo_favorites.rowid = weibo_fts.rowid 
                    WHERE weibo_fts MATCH ?
                    """, 
                    (query,)
                ).fetchone()["total"]
                
                # 获取匹配的微博，并使用snippet函数获取高亮的文本片段
                offset = (page - 1) * per_page
                rows = cursor.execute(
                    """
                    SELECT 
                        weibo_favorites.*,
                        snippet(weibo_fts, -1, '<mark>', '</mark>', '...', 64) as matched_text,
                        bm25(weibo_fts) as relevance
                    FROM weibo_favorites 
                    JOIN weibo_fts ON weibo_favorites.rowid = weibo_fts.rowid 
                    WHERE weibo_fts MATCH ? 
                    ORDER BY relevance DESC, created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (query, per_page, offset)
                ).fetchall()
                
                # 获取每条微博的图片
                for row in rows:
                    row["images"] = self._get_weibo_images(cursor, row["id"], use_thumbnail=True)
                
                return rows, total
                
            except Exception as e:
                logger.error(f"搜索微博失败: {e}")
                return [], 0


# 创建全局数据库实例
db = WeiboDB()
