# database.py

import sqlite3
from config import DATABASE_PATH

def create_table():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weibo_favorites (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            url TEXT,
            user_name TEXT,
            user_id TEXT,
            is_long_text BOOLEAN,
            text TEXT,
            text_html TEXT,
            source TEXT,
            links TEXT,
            collected_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_weibo(weibo):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO weibo_favorites (
            id, created_at, url, user_name, user_id, is_long_text, text, text_html,
            source, links, collected_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        weibo['collected_at']
    ))
    conn.commit()
    conn.close()