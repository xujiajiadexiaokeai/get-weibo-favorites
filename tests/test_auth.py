"""测试认证模块"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from weibo_favorites.crawler.auth import CookieManager, get_weibo_uid_from_env


@pytest.fixture
def mock_cookies():
    """模拟的cookies数据"""
    return [
        {
            "name": "SUB",
            "value": "test_sub_value",
            "domain": ".weibo.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None",
        },
        {
            "name": "WBPSESS",
            "value": "test_session_value",
            "domain": "weibo.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "Lax",
        },
    ]


@pytest.fixture
def mock_cookies_file(tmp_path: Path, mock_cookies):
    """创建模拟的cookies文件"""
    cookies_file = tmp_path / "weibo_cookies.json"
    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(mock_cookies, f)
    return cookies_file


@pytest.fixture
def mock_config(tmp_path: Path, mock_cookies_file):
    """模拟配置"""
    with patch("weibo_favorites.config.COOKIES_FILE", mock_cookies_file):
        yield


@pytest.fixture
def cookie_manager(mock_config):
    """创建CookieManager实例"""
    return CookieManager()


def test_cookie_manager_init(cookie_manager, mock_cookies):
    """测试CookieManager初始化"""
    assert cookie_manager.cookies == mock_cookies
    assert not cookie_manager.is_valid
    assert cookie_manager.last_check_time is None


def test_create_session(cookie_manager, mock_cookies):
    """测试创建会话"""
    session = cookie_manager.create_session()
    assert isinstance(session, requests.Session)

    # 验证cookies是否正确设置
    for cookie in mock_cookies:
        assert session.cookies.get(cookie["name"]) == cookie["value"]

    # 验证请求头是否正确设置
    headers = session.headers
    assert "User-Agent" in headers
    assert headers["Accept"] == "application/json, text/plain, */*"
    assert headers["Accept-Language"] == "zh-CN,zh;q=0.9,en;q=0.8"
    assert headers["Referer"] == "https://weibo.com/fav"


def test_create_session_with_invalid_cookies(cookie_manager):
    """测试使用无效的cookie创建会话"""
    cookie_manager.cookies = [{"invalid": "cookie"}]
    session = cookie_manager.create_session()
    assert isinstance(session, requests.Session)
    assert len(session.cookies) == 0  # 无效的cookie不应该被设置


def test_load_cookies_success(cookie_manager, mock_cookies):
    """测试成功加载cookies"""
    assert cookie_manager.load_cookies()
    assert cookie_manager.cookies == mock_cookies


def test_load_cookies_file_not_found(tmp_path: Path):
    """测试加载不存在的cookies文件"""
    with patch("weibo_favorites.config.COOKIES_FILE", tmp_path / "not_exist.json"):
        manager = CookieManager()
        assert not manager.load_cookies()
        assert manager.cookies == []


def test_load_cookies_invalid_format(tmp_path: Path):
    """测试加载格式错误的cookies文件"""
    cookies_file = tmp_path / "invalid_cookies.json"
    with open(cookies_file, "w", encoding="utf-8") as f:
        f.write("invalid json")

    with patch("weibo_favorites.config.COOKIES_FILE", cookies_file):
        manager = CookieManager()
        assert not manager.load_cookies()
        assert manager.cookies == []


def test_save_cookies(cookie_manager, mock_cookies_file):
    """测试保存cookies"""
    cookie_manager.cookies.append(
        {
            "name": "new_cookie",
            "value": "new_value",
            "domain": ".weibo.com",
            "path": "/",
        }
    )
    assert cookie_manager.save_cookies()

    # 验证文件内容
    with open(mock_cookies_file, "r", encoding="utf-8") as f:
        saved_cookies = json.load(f)
    assert len(saved_cookies) == 3
    assert any(c["name"] == "new_cookie" for c in saved_cookies)


@pytest.mark.parametrize(
    "response_data,expected_valid",
    [
        ({"data": {"user": {"screen_name": "test_user"}}}, True),
        ({"error": "Invalid cookies"}, False),
        ({}, False),
    ],
)
def test_check_validity(cookie_manager, response_data, expected_valid):
    """测试cookie有效性检查"""
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.get", return_value=mock_response), patch(
        "weibo_favorites.crawler.auth.get_weibo_uid_from_env", return_value="123456"
    ):
        valid, _ = cookie_manager.check_validity()
        assert valid == expected_valid
        if valid:
            assert cookie_manager.user_info == response_data["data"]["user"]
            assert cookie_manager.is_valid
            assert cookie_manager.last_check_time is not None


def test_check_validity_request_error(cookie_manager):
    """测试cookie有效性检查请求错误"""
    with patch(
        "requests.Session.get", side_effect=requests.RequestException("Network error")
    ), patch(
        "weibo_favorites.crawler.auth.get_weibo_uid_from_env", return_value="123456"
    ):
        valid, error = cookie_manager.check_validity()
        assert not valid
        assert "Network error" in error
        assert not cookie_manager.is_valid


def test_check_validity_no_uid(cookie_manager):
    """测试无法获取UID的情况"""
    with patch(
        "weibo_favorites.crawler.auth.get_weibo_uid_from_env",
        side_effect=Exception("WEIBO_UID必须提供"),
    ):
        valid, error = cookie_manager.check_validity()
        assert not valid
        assert "WEIBO_UID必须提供" in error
        assert not cookie_manager.is_valid


def test_get_weibo_uid_from_env():
    """测试从环境变量获取UID"""
    with patch.dict(os.environ, {"WEIBO_UID": "123456"}):
        assert get_weibo_uid_from_env() == "123456"


def test_get_weibo_uid_from_env_missing():
    """测试环境变量中没有UID的情况"""
    with patch.dict(os.environ, clear=True):
        with pytest.raises(Exception, match="WEIBO_UID必须提供"):
            get_weibo_uid_from_env()


def test_update_cookies_from_response(cookie_manager):
    """测试从响应更新cookies"""
    # 创建模拟的响应对象
    mock_response = MagicMock(spec=requests.Response)

    # 创建模拟的cookie对象
    class MockCookie:
        def __init__(self, name, value):
            self.name = name
            self.value = value
            self.domain = ".weibo.com"
            self.path = "/"
            self.secure = True
            self.expires = None
            self._rest = {"HttpOnly": True}

        def has_nonstandard_attr(self, attr):
            return attr in self._rest

    # 创建模拟的cookies集合
    mock_cookie = MockCookie("new_cookie", "new_value")
    mock_cookies = MagicMock(spec=requests.cookies.RequestsCookieJar)
    mock_cookies.__iter__.return_value = [mock_cookie]
    mock_cookies.get_dict.return_value = {"new_cookie": "new_value"}
    mock_response.cookies = mock_cookies

    # 测试更新cookies
    cookie_manager._update_cookies_from_response(mock_response)

    # 验证cookies是否被正确更新
    new_cookie = next(
        (c for c in cookie_manager.cookies if c["name"] == "new_cookie"), None
    )
    assert new_cookie is not None
    assert new_cookie["value"] == "new_value"
    assert new_cookie["domain"] == ".weibo.com"
    assert new_cookie["path"] == "/"
    assert new_cookie["secure"] is True
    assert new_cookie["httpOnly"] is True
    assert new_cookie["sameSite"] == "None"  # secure为True时，sameSite应为None


def test_get_status(cookie_manager):
    """测试获取状态信息"""
    cookie_manager.is_valid = True
    cookie_manager.last_check_time = datetime.now()
    cookie_manager.user_info = {"screen_name": "test_user"}

    status = cookie_manager.get_status()
    assert status["is_valid"]
    assert status["last_check_time"]
    assert status["user_info"] == {"screen_name": "test_user"}
    assert status["cookies_count"] == 2  # 来自mock_cookies的两个cookie


def test_get_status_auto_check(cookie_manager):
    """测试状态获取时的自动检查"""
    cookie_manager.is_valid = True
    cookie_manager.last_check_time = datetime.now() - timedelta(minutes=10)

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"user": {"screen_name": "test_user"}}}
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.get", return_value=mock_response), patch(
        "weibo_favorites.crawler.auth.get_weibo_uid_from_env", return_value="123456"
    ):
        status = cookie_manager.get_status()
        assert status["is_valid"]
        assert status["user_info"] == {"screen_name": "test_user"}
