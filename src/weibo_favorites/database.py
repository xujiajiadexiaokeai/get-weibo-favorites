# database.py

import sqlite3
from typing import List, Dict, Any
from . import config

def create_table():
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weibo_favorites (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            url TEXT,
            user_name TEXT,
            user_id TEXT,
            is_long_text INTEGER,
            text TEXT,
            text_html TEXT,
            source TEXT,
            links TEXT,
            collected_at TEXT,
            text_length INTEGER,
            crawled INTEGER DEFAULT 0,
            crawl_status TEXT DEFAULT 'pending',
            updated_at TEXT
        )''')
    conn.commit()
    conn.close()

def save_weibo(weibo: Dict[str, Any]):
    """保存单条微博数据"""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO weibo_favorites (
                id, created_at, url, user_name, user_id, is_long_text, text, text_html,
                source, links, collected_at, text_length, crawled, crawl_status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            weibo['id'],
            weibo['created_at'],
            weibo['url'],
            weibo['user_name'],
            weibo['user_id'],
            weibo['is_long_text'],
            weibo['text'],
            weibo['text_html'],
            weibo['source'],
            ','.join(weibo['links']),
            weibo['collected_at'],
            len(weibo['text']),
            weibo.get('crawled', False),
            weibo.get('crawl_status', 'completed' if not weibo['is_long_text'] else 'pending'),
            weibo.get('updated_at')
        ))
        conn.commit()
    finally:
        conn.close()

def update_weibo_content(weibo_id: str, update_data: Dict[str, Any]):
    """更新微博内容
    
    Args:
        weibo_id: 微博ID
        update_data: 要更新的数据字段
    """
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # 构建更新语句
        update_fields = []
        values = []
        for key, value in update_data.items():
            if key in ['text', 'text_length', 'crawled', 'crawl_status', 'updated_at']:
                update_fields.append(f"{key} = ?")
                values.append(value)
        
        if not update_fields:
            return
            
        values.append(weibo_id)  # WHERE 条件的值
        
        sql = f'''
            UPDATE weibo_favorites
            SET {', '.join(update_fields)}
            WHERE id = ?
        '''
        
        cursor.execute(sql, values)
        conn.commit()
        
    finally:
        conn.close()

def get_pending_long_text_weibos() -> List[Dict[str, Any]]:
    """获取待处理的长文本微博列表"""
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, url, text_length, crawl_status
            FROM weibo_favorites
            WHERE is_long_text = 1 AND crawl_status = 'pending'
            ORDER BY created_at DESC
        ''')
        
        columns = ['id', 'url', 'text_length', 'crawl_status']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    finally:
        conn.close()