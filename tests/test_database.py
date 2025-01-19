import pytest
from datetime import datetime

from weibo_favorites import config
from weibo_favorites.database import (
    get_pending_long_text_weibos,
    save_weibo,
    update_weibo_content,
    save_image_metadata,
    update_image_process_result,
    update_image_process_status,
    get_connection,
)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_mode():
    """在所有测试用例执行完后，禁用测试模式"""
    yield
    print("禁用测试模式")
    config.settings.disable_test_mode()


@pytest.fixture(autouse=True)
def setup_test_db():
    """设置测试数据库"""
    # 设置测试配置
    test_db_path = config.settings.DATA_DIR / "test_weibo_favorites.db"
    
    # 确保测试数据库不存在
    if test_db_path.exists():
        test_db_path.unlink()

    # 启用测试模式
    config.settings.enable_test_mode(db_path=test_db_path)
    print(f"启用测试模式，测试数据库路径：{config.settings.DATABASE_FILE}")

    # 创建数据库表
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
            )
            """
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
            )
            """
        )
        conn.commit()

    yield

    # 清理测试数据库
    if test_db_path.exists():
        test_db_path.unlink()


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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 保存微博
    save_weibo(test_weibo)

    # 验证保存结果
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, mblogid, is_long_text, text
            FROM weibo_favorites
            WHERE id = ?
            """,
            (test_weibo["id"],)
        )
        result = cursor.fetchone()

    assert result is not None
    assert result[0] == test_weibo["id"]  # id
    assert result[1] == test_weibo["mblogid"]  # mblogid
    assert result[2] == test_weibo["is_long_text"]  # is_long_text
    assert result[3] == test_weibo["text"]  # text


def test_update_weibo_content():
    """测试更新微博内容"""
    # 先插入一条测试数据
    weibo_id = "123456789"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO weibo_favorites (id, is_long_text, text, crawl_status)
            VALUES (?, ?, ?, ?)
            """,
            (weibo_id, True, "原始内容", "pending"),
        )
        conn.commit()

    # 更新内容
    update_data = {
        "long_text": "这是更新后的长文本内容",
        "text_length": 13,
        "crawled": True,
        "crawl_status": "completed",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    update_weibo_content(weibo_id, update_data)

    # 验证更新结果
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT long_text, text_length, crawled, crawl_status FROM weibo_favorites WHERE id = ?",
            (weibo_id,),
        )
        result = cursor.fetchone()

    assert result is not None
    assert result[0] == update_data["long_text"]
    assert result[1] == update_data["text_length"]
    assert result[2] == update_data["crawled"]
    assert result[3] == update_data["crawl_status"]


def test_save_and_update_image():
    """测试图片保存和更新"""
    # 准备测试数据
    image_data = {
        "weibo_id": "123456789",
        "pic_id": "pic123",
        "url": "https://example.com/image.jpg",
        "width": 800,
        "height": 600,
        "content_type": "image/jpeg",
        "content": b"test_image_content"
    }

    # 保存图片元数据
    save_image_metadata(image_data)

    # 准备处理结果
    processed_images = {
        "thumbnail": b"thumbnail_data",
        "compressed": b"compressed_data"
    }

    # 更新处理结果
    update_image_process_result(image_data["weibo_id"], image_data["pic_id"], processed_images)

    # 验证结果
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT weibo_id, pic_id, url, width, height, content_type, 
                   raw_content, thumbnail, compressed, process_status
            FROM weibo_images 
            WHERE weibo_id = ? AND pic_id = ?
            """,
            (image_data["weibo_id"], image_data["pic_id"])
        )
        result = cursor.fetchone()

    assert result is not None
    assert result[0] == image_data["weibo_id"]
    assert result[1] == image_data["pic_id"]
    assert result[2] == image_data["url"]
    assert result[3] == image_data["width"]
    assert result[4] == image_data["height"]
    assert result[5] == image_data["content_type"]
    assert result[6] == image_data["content"]
    assert result[7] == processed_images["thumbnail"]
    assert result[8] == processed_images["compressed"]
    assert result[9] == "success"


def test_update_image_process_status():
    """测试更新图片处理状态"""
    # 准备测试数据
    image_data = {
        "weibo_id": "123456789",
        "pic_id": "pic123",
        "url": "https://example.com/image.jpg",
        "content_type": "image/jpeg",
        "content": b"test_image_content"
    }

    # 保存图片元数据
    save_image_metadata(image_data)

    # 更新处理状态
    error_msg = "处理失败：图片格式不支持"
    update_image_process_status(image_data["weibo_id"], image_data["pic_id"], error_msg)

    # 验证结果
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT process_status FROM weibo_images WHERE weibo_id = ? AND pic_id = ?",
            (image_data["weibo_id"], image_data["pic_id"])
        )
        result = cursor.fetchone()

    assert result is not None
    assert result[0] == f"error: {error_msg}"


def test_get_pending_long_text_weibos():
    """测试获取待处理的长文本微博"""
    # 插入测试数据
    with get_connection() as conn:
        cursor = conn.cursor()
        test_data = [
            ("1", "A1", True, "pending"),
            ("2", "A2", True, "completed"),
            ("3", "A3", False, "pending"),
            ("4", "A4", True, "pending"),
        ]

        for weibo_id, mblogid, is_long_text, status in test_data:
            cursor.execute(
                """
                INSERT INTO weibo_favorites (id, mblogid, is_long_text, crawl_status)
                VALUES (?, ?, ?, ?)
                """,
                (weibo_id, mblogid, is_long_text, status),
            )
        conn.commit()

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
