"""爬虫模块测试"""
import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from weibo_favorites import config
from weibo_favorites.crawler.auth import create_session, load_cookies
from weibo_favorites.crawler.crawler import (
    check_duplicate,
    crawl_favorites,
    get_favorites,
    load_crawler_state,
    parse_weibo,
    parse_weibo_time,
    save_crawler_state,
)


def test_unit_parse_weibo_time():
    """测试微博时间解析"""
    # 测试正常时间格式
    time_str = "Sun Dec 01 12:09:53 +0800 2024"
    result = parse_weibo_time(time_str)
    assert result == "2024-12-01 12:09:53"

    # 测试异常时间格式
    invalid_time = "Invalid Time Format"
    result = parse_weibo_time(invalid_time)
    assert result == invalid_time  # 应该返回原始字符串


def test_unit_parse_weibo():
    """测试微博数据解析"""
    # 准备测试数据
    test_data = {
        "idstr": "123456",
        "mblogid": "abc123",
        "created_at": "Sun Dec 01 12:09:53 +0800 2024",
        "user": {"idstr": "user123", "screen_name": "TestUser"},
        "isLongText": True,
        "text_raw": "This is a test weibo",
        "text": "<p>This is a test weibo</p>",
        "source": "iPhone客户端",
        "url_struct": [
            {"long_url": "http://example.com/1"},
            {"long_url": "http://example.com/2"},
        ],
    }

    # 解析微博数据
    result = parse_weibo(test_data)

    # 验证基本字段
    assert result["id"] == "123456"
    assert result["mblogid"] == "abc123"
    assert result["created_at"] == "2024-12-01 12:09:53"
    assert result["user_id"] == "user123"
    assert result["user_name"] == "TestUser"
    assert result["is_long_text"] == True
    assert result["text"] == "This is a test weibo"
    assert result["text_html"] == "<p>This is a test weibo</p>"
    assert result["source"] == "iPhone客户端"
    assert len(result["links"]) == 2
    assert result["links"][0] == "http://example.com/1"

    # 验证URL格式
    assert result["url"] == "https://weibo.com/user123/abc123"

    # 验证爬取状态
    assert result["crawl_status"] == "pending"
    assert result["crawled"] == False

    # 测试异常情况
    invalid_data = {"idstr": "123"}  # 缺少必要字段
    result = parse_weibo(invalid_data)
    # 验证基本字段仍然存在
    assert result["id"] == "123"
    assert result["is_long_text"] == False  # 默认值
    assert result["crawl_status"] == "completed"  # 默认值
    assert result["text"] == ""  # 默认空字符串


def test_unit_check_duplicate():
    """测试重复检查"""
    # 测试找到重复
    assert check_duplicate("123", "123") == True

    # 测试未找到重复
    assert check_duplicate("123", "456") == False

    # 测试空ID
    assert check_duplicate(None, "123") == False
    assert check_duplicate("", "123") == False


def test_unit_get_favorites():
    """测试获取收藏列表"""
    # 模拟成功响应
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
    mock_response.raise_for_status.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    # 测试正常获取
    result = get_favorites(mock_session, page=1)
    assert len(result) == 2
    mock_session.get.assert_called_once_with(config.BASE_URL, params={"page": 1})

    # 测试请求异常
    mock_session.get.side_effect = Exception("Network Error")
    result = get_favorites(mock_session, page=1)
    assert result == []


def test_unit_crawler_state():
    """测试爬虫状态管理"""
    test_state = {"last_id": "123456", "last_crawl_time": "2024-12-29 11:30:00"}

    # 测试保存状态
    m = mock_open()
    with patch("builtins.open", m):
        save_crawler_state(test_state)

    # 验证写入操作
    m.assert_called_once_with(config.CRAWLER_STATE_FILE, "w", encoding="utf-8")
    handle = m()
    # 验证写入的内容而不是调用次数
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    expected_content = json.dumps(test_state, ensure_ascii=False, indent=2)
    assert written_content == expected_content

    # 测试加载状态 - 正常情况
    m = mock_open(read_data=json.dumps(test_state))
    with patch("builtins.open", m):
        loaded_state = load_crawler_state()
    assert loaded_state == test_state

    # 测试加载状态 - 文件不存在
    with patch("builtins.open", side_effect=FileNotFoundError):
        loaded_state = load_crawler_state()
    assert loaded_state == {"last_id": None, "last_crawl_time": None}

    # 测试加载状态 - JSON解析错误
    m = mock_open(read_data="invalid json")
    with patch("builtins.open", m):
        loaded_state = load_crawler_state()
    assert loaded_state == {"last_id": None, "last_crawl_time": None}


def test_unit_parse_weibo_edge_cases():
    """测试微博数据解析的边界情况"""
    # 测试空数据
    empty_data = {}
    result = parse_weibo(empty_data)
    assert result["id"] == ""
    assert result["text"] == ""
    assert result["crawl_status"] == "completed"

    # 测试None值
    none_data = {"idstr": None, "mblogid": None, "user": None, "text_raw": None}
    result = parse_weibo(none_data)
    assert result["id"] == ""
    assert result["mblogid"] == ""
    assert result["text"] == ""

    # 测试特殊字符
    special_data = {
        "idstr": "123",
        "text_raw": "包含特殊字符：\n\t\r",
        "user": {"idstr": "user123", "screen_name": "用户名\n"},
    }
    result = parse_weibo(special_data)
    assert result["id"] == "123"
    assert result["text"] == "包含特殊字符：\n\t\r"
    assert result["user_name"] == "用户名\n"


def test_unit_parse_weibo_time_edge_cases():
    """测试时间解析的边界情况"""
    # 测试空字符串
    assert parse_weibo_time("") == ""

    # 测试None值
    assert parse_weibo_time(None) == None

    # 测试不同时区
    time_str = "Sun Dec 01 12:09:53 +0000 2024"  # UTC时间
    result = parse_weibo_time(time_str)
    assert result == "2024-12-01 12:09:53"

    # 测试非标准格式
    invalid_formats = ["2024-12-01", "12:09:53", "Invalid Date", "Sun Dec 01 2024"]
    for time_str in invalid_formats:
        result = parse_weibo_time(time_str)
        assert result == time_str  # 应该返回原始字符串


@pytest.fixture
def mock_queue():
    """模拟长文本处理队列"""
    queue = MagicMock()
    queue.add_task.return_value = "job123"
    queue.get_queue_status.return_value = {"pending": 1, "finished": 0}
    return queue


@pytest.fixture
def mock_session():
    """模拟请求会话"""
    session = MagicMock()
    return session


def test_unit_crawl_favorites_basic(mock_queue, mock_session):
    """测试基本的收藏爬取功能"""
    # 准备测试数据
    test_weibo = {
        "idstr": "123456",
        "mblogid": "abc123",
        "created_at": "Sun Dec 01 12:09:53 +0800 2024",
        "user": {"idstr": "user123", "screen_name": "TestUser"},
        "isLongText": True,
        "text_raw": "This is a test weibo",
    }

    # 模拟get_favorites的返回值
    mock_session.get.return_value.json.return_value = {"data": [test_weibo]}

    # 模拟文件操作
    state_data = {"last_id": None, "last_crawl_time": None}
    m = mock_open(read_data=json.dumps(state_data))

    with patch("builtins.open", m), patch(
        "weibo_favorites.crawler.crawler.create_session", return_value=mock_session
    ), patch("weibo_favorites.crawler.crawler.save_weibo") as mock_save_weibo:
        # 执行爬取
        result = crawl_favorites(
            cookies=[{"cookie": "test"}], ltp_queue=mock_queue, page_number=1
        )

        # 验证结果
        assert len(result) == 1
        assert result[0]["id"] == "123456"
        assert result[0]["is_long_text"] == True

        # 验证函数调用
        mock_session.get.assert_called_once()
        mock_queue.add_task.assert_called_once()
        mock_save_weibo.assert_called_once()


def test_unit_crawl_favorites_duplicate_check(mock_queue, mock_session):
    """测试重复内容检查功能"""
    # 准备测试数据
    test_weibos = [
        {
            "idstr": "123",
            "created_at": "Sun Dec 01 12:09:53 +0800 2024",
            "user": {"idstr": "user1", "screen_name": "User1"},
        },
        {
            "idstr": "456",
            "created_at": "Sun Dec 01 12:10:53 +0800 2024",
            "user": {"idstr": "user2", "screen_name": "User2"},
        },
    ]

    # 模拟已有上次爬取记录
    state_data = {"last_id": "456", "last_crawl_time": "2024-12-29 11:00:00"}

    # 模拟get_favorites的返回值
    mock_session.get.return_value.json.return_value = {"data": test_weibos}

    with patch("builtins.open", mock_open(read_data=json.dumps(state_data))), patch(
        "weibo_favorites.crawler.crawler.create_session", return_value=mock_session
    ), patch("weibo_favorites.crawler.crawler.save_weibo") as mock_save_weibo:
        # 执行爬取
        result = crawl_favorites(
            cookies=[{"cookie": "test"}], ltp_queue=mock_queue, page_number=1
        )

        # 验证结果：应该只保存第一条微博
        assert len(result) == 1
        assert result[0]["id"] == "123"

        # 验证save_weibo只被调用一次
        assert mock_save_weibo.call_count == 1


def test_unit_crawl_favorites_error_handling(mock_queue, mock_session):
    """测试错误处理"""
    # 模拟网络错误
    mock_session.get.side_effect = Exception("Network Error")

    with patch("builtins.open", mock_open(read_data="{}")), patch(
        "weibo_favorites.crawler.crawler.create_session", return_value=mock_session
    ):
        # 执行爬取
        result = crawl_favorites(
            cookies=[{"cookie": "test"}], ltp_queue=mock_queue, page_number=1
        )

        # 验证结果
        assert result == []

        # 验证队列操作未执行
        mock_queue.add_task.assert_not_called()


def test_unit_crawl_favorites_empty_response(mock_queue, mock_session):
    """测试空响应处理"""
    # 模拟空响应
    mock_session.get.return_value.json.return_value = {"data": []}

    with patch("builtins.open", mock_open(read_data="{}")), patch(
        "weibo_favorites.crawler.crawler.create_session", return_value=mock_session
    ):
        # 执行爬取
        result = crawl_favorites(
            cookies=[{"cookie": "test"}], ltp_queue=mock_queue, page_number=1
        )

        # 验证结果
        assert result == []

        # 验证队列操作未执行
        mock_queue.add_task.assert_not_called()


def test_unit_crawl_favorites_queue_error(mock_queue, mock_session):
    """测试队列错误处理"""
    # 准备测试数据
    test_weibo = {
        "idstr": "123",
        "created_at": "Sun Dec 01 12:09:53 +0800 2024",
        "user": {"idstr": "user1", "screen_name": "User1"},
        "isLongText": True,
    }

    # 模拟队列错误
    mock_queue.add_task.side_effect = Exception("Queue Error")
    mock_session.get.return_value.json.return_value = {"data": [test_weibo]}

    with patch("builtins.open", mock_open(read_data="{}")), patch(
        "weibo_favorites.crawler.crawler.create_session", return_value=mock_session
    ), patch("weibo_favorites.crawler.crawler.save_weibo") as mock_save_weibo:
        # 执行爬取
        result = crawl_favorites(
            cookies=[{"cookie": "test"}], ltp_queue=mock_queue, page_number=1
        )

        # 验证结果：即使队列出错，也应该保存微博
        assert len(result) == 1
        assert result[0]["id"] == "123"
        mock_save_weibo.assert_called_once()


# TODO: 集成测试（暂时不测试，稍后修改）
# @pytest.fixture
# def debug_file(tmp_path):
#     """用于保存调试数据的文件路径，使用临时目录"""
#     return tmp_path / "test_favorites.json"

# def test_integration_get_first_page(debug_file, capsys):
#     """集成测试：获取第一页收藏数据"""
#     # 加载cookies
#     cookies = load_cookies()
#     if not cookies:
#         pytest.skip("无法加载cookies，请先运行 auth.py 获取cookies")

#     session = None
#     try:
#         # 创建会话
#         session = create_session(cookies)
#         assert session is not None, "创建会话失败"

#         # 获取第一页数据
#         print("开始获取第一页数据...")  # 这会被 capsys 捕获
#         favorites = get_favorites(session, page=1)

#         # 验证返回数据
#         assert isinstance(favorites, list), "返回数据应该是列表类型"
#         if len(favorites) > 0:
#             # 验证第一条收藏的数据结构
#             first_item = favorites[0]
#             weibo = parse_weibo(first_item) # 解析微博
#             assert isinstance(weibo, dict), "收藏数据应该是字典类型"
#             required_fields = ["id", "mblogid", "created_at", "text", "user_name", "user_id"]
#             for field in required_fields:
#                 assert field in weibo, f"收藏数据缺少必要字段: {field}"
#                 assert weibo[field], f"字段 {field} 不应为空"

#             # 保存调试数据到临时文件
#             with open(debug_file, "w", encoding="utf-8") as f:
#                 json.dump(favorites, f, ensure_ascii=False, indent=2)
#             print(f"调试数据已保存至: {debug_file}")  # 这会被 capsys 捕获

#             # 验证输出内容
#             captured = capsys.readouterr()
#             assert "开始获取第一页数据..." in captured.out
#             assert "调试数据已保存至" in captured.out
#         else:
#             pytest.skip("未获取到任何收藏数据（用户可能没有收藏）")

#     except Exception as e:
#         # 如果有调试数据，在错误信息中包含文件路径
#         error_msg = f"测试失败: {str(e)}"
#         if debug_file.exists():
#             error_msg += f"\n调试数据已保存至: {debug_file}"
#         pytest.fail(error_msg)
#     finally:
#         if session:
#             session.close()
