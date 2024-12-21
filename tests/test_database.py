import pytest
import os
import sqlite3
from datetime import datetime
from weibo_favorites import config
from weibo_favorites.database import save_weibo, update_weibo_content, get_pending_long_text_weibos

@pytest.fixture(autouse=True)
def setup_test_db():
    """设置测试数据库"""
    # 保存原始数据库路径
    original_db_path = config.DATABASE_FILE
    
    # 设置测试数据库路径
    test_db_path = config.DATA_DIR / 'test_weibo_favorites.db'
    config.DATABASE_FILE = test_db_path
    
    # 确保测试数据库不存在
    if test_db_path.exists():
        test_db_path.unlink()
    
    # 创建数据库表
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute('''
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
        )
    ''')
    conn.commit()
    conn.close()
    
    yield
    
    # 清理测试数据库
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # 恢复原始数据库路径
    config.DATABASE_FILE = original_db_path

def test_save_weibo():
    """测试保存微博数据"""
    test_weibo = {
        "id": "123456789",
        "mblogid": "ABC123",
        "created_at": "2024-12-21 10:00:00",
        "url": "https://weibo.com/123456789/ABC123",
        "user_name": "测试用户",
        "user_id": "987654321",
        "is_long_text": True,
        "text": "这是一条测试微博",
        "text_html": "<p>这是一条测试微博</p>",
        "long_text": "",
        "source": "微博 weibo.com",
        "links": ["https://example.com"],
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text_length": 8,
        "crawled": False,
        "crawl_status": "pending",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存微博
    save_weibo(test_weibo)
    
    # 验证保存结果
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM weibo_favorites WHERE id = ?", (test_weibo["id"],))
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] == test_weibo["id"]  # id
    assert result[1] == test_weibo["mblogid"]  # mblogid
    assert result[6] == test_weibo["is_long_text"]  # is_long_text
    assert result[7] == test_weibo["text"]  # text

def test_update_weibo_content():
    """测试更新微博内容"""
    # 先插入一条测试数据
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    weibo_id = "123456789"
    cursor.execute('''
        INSERT INTO weibo_favorites (id, is_long_text, text, crawl_status)
        VALUES (?, ?, ?, ?)
    ''', (weibo_id, True, "原始内容", "pending"))
    conn.commit()
    conn.close()
    
    # 更新内容
    update_data = {
        "long_text": "这是更新后的长文本内容",
        "text_length": 13,
        "crawled": True,
        "crawl_status": "completed",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    update_weibo_content(weibo_id, update_data)
    
    # 验证更新结果
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT long_text, text_length, crawled, crawl_status FROM weibo_favorites WHERE id = ?", (weibo_id,))
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] == update_data["long_text"]
    assert result[1] == update_data["text_length"]
    assert result[2] == update_data["crawled"]
    assert result[3] == update_data["crawl_status"]

def test_get_pending_long_text_weibos():
    """测试获取待处理的长文本微博"""
    # 插入测试数据
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    test_data = [
        ("1", "A1", True, "pending"),
        ("2", "A2", True, "completed"),
        ("3", "A3", False, "pending"),
        ("4", "A4", True, "pending")
    ]
    
    for weibo_id, mblogid, is_long_text, status in test_data:
        cursor.execute('''
            INSERT INTO weibo_favorites (id, mblogid, is_long_text, crawl_status)
            VALUES (?, ?, ?, ?)
        ''', (weibo_id, mblogid, is_long_text, status))
    conn.commit()
    conn.close()
    
    # 获取待处理的长文本微博
    pending_weibos = get_pending_long_text_weibos()
    
    # 验证结果
    assert len(pending_weibos) == 2  # 应该只有2条待处理的长文本
    assert all(weibo["crawl_status"] == "pending" for weibo in pending_weibos)
    assert all(weibo["is_long_text"] == 1 for weibo in pending_weibos)
    
    # 验证返回的字段
    expected_ids = {"1", "4"}
    returned_ids = {weibo["id"] for weibo in pending_weibos}
    assert returned_ids == expected_ids
