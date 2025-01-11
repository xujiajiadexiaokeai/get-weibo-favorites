"""数据库操作模块"""

import sqlite3
import base64
from typing import Dict, List, Optional
from datetime import datetime

from .. import config
from ..utils import LogManager

logger = LogManager.setup_logger("web")


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict:
    """将数据库查询结果转换为字典"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_db() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = dict_factory
    return conn


def get_weibo_images(cursor: sqlite3.Cursor, weibo_id: str, use_thumbnail: bool = True) -> List[Dict]:
    """获取微博的图片信息
    
    Args:
        cursor: 数据库游标
        weibo_id: 微博ID
        use_thumbnail: 是否使用缩略图，True则返回thumbnail字段，False则返回compressed字段
    """
    cursor.execute(
        """
        SELECT 
            pic_id,
            url,
            width,
            height,
            content_type,
            thumbnail,
            compressed,
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
        img_data = image['thumbnail'] if use_thumbnail else image['compressed']
        if img_data:
            # 转换为base64字符串
            b64_data = base64.b64encode(img_data).decode('utf-8')
            image['data_url'] = f"data:{image['content_type']};base64,{b64_data}"
        else:
            # 如果没有处理好的图片数据，使用原始URL
            image['data_url'] = image['url']
            
        # 清理不需要的字段
        del image['thumbnail']
        del image['compressed']
        del image['url']
    
    return images


def get_weibo_by_id(weibo_id: str) -> Optional[Dict]:
    """根据ID获取单条微博信息"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM weibo_favorites
                WHERE id = ?
                """,
                (weibo_id,)
            )
            weibo = cursor.fetchone()
            
            if weibo:
                # 获取图片信息（使用压缩后的图片）
                weibo['images'] = get_weibo_images(cursor, weibo_id, use_thumbnail=False)
                    
                # 格式化时间
                if weibo.get('created_at'):
                    created_at = datetime.fromisoformat(weibo['created_at'])
                    weibo['created_at'] = created_at.strftime('%Y-%m-%d %H:%M:%S')
                    
            return weibo
    except Exception as e:
        logger.error(f"获取微博信息失败: {e}")
        return None


def get_favorites(page: int = 1, per_page: int = 20) -> tuple[List[Dict], int]:
    """获取收藏列表"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 获取总数
            cursor.execute("SELECT COUNT(*) as total FROM weibo_favorites")
            total = cursor.fetchone()['total']
            
            # 获取分页数据
            offset = (page - 1) * per_page
            cursor.execute(
                """
                SELECT *
                FROM weibo_favorites
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (per_page, offset)
            )
            items = cursor.fetchall()
            
            # 处理每条微博的数据
            for item in items:
                # 获取图片信息（使用缩略图）
                item['images'] = get_weibo_images(cursor, item['id'], use_thumbnail=True)
                    
                # 格式化时间
                if item.get('created_at'):
                    created_at = datetime.fromisoformat(item['created_at'])
                    item['created_at'] = created_at.strftime('%Y-%m-%d %H:%M:%S')
            
            return items, total
    except Exception as e:
        logger.error(f"获取收藏列表失败: {e}")
        return [], 0
