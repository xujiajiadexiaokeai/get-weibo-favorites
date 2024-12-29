"""测试认证模块"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from weibo_favorites.crawler.auth import CookieManager


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
            "sameSite": "None"
        },
        {
            "name": "WBPSESS",
            "value": "test_session_value",
            "domain": "weibo.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "Lax"
        }
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
    assert cookie_manager._session is not None
    assert not cookie_manager.is_valid
    assert cookie_manager.last_check_time is None


def test_load_cookies_success(cookie_manager, mock_cookies):
    """测试成功加载cookies"""
    assert cookie_manager.load_cookies()
    assert cookie_manager.cookies == mock_cookies


def test_load_cookies_file_not_found(tmp_path: Path):
    """测试加载不存在的cookies文件"""
    with patch("weibo_favorites.config.COOKIES_FILE", tmp_path / "not_exist.json"):
        manager = CookieManager()
        assert not manager.load_cookies()


def test_save_cookies(cookie_manager, mock_cookies_file):
    """测试保存cookies"""
    cookie_manager.cookies.append({
        "name": "new_cookie",
        "value": "new_value",
        "domain": ".weibo.com",
        "path": "/"
    })
    assert cookie_manager.save_cookies()
    
    # 验证文件内容
    with open(mock_cookies_file, "r", encoding="utf-8") as f:
        saved_cookies = json.load(f)
    assert len(saved_cookies) == 3
    assert any(c["name"] == "new_cookie" for c in saved_cookies)


@pytest.mark.parametrize("response_data,expected_valid", [
    ({"data": {"user": {"screen_name": "test_user"}}}, True),
    ({"error": "Invalid cookies"}, False),
    ({}, False)
])
def test_check_validity(cookie_manager, response_data, expected_valid):
    """测试cookie有效性检查"""
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status.return_value = None
    
    with patch("requests.Session.get", return_value=mock_response):
        valid, _ = cookie_manager.check_validity()
        assert valid == expected_valid
        if valid:
            assert cookie_manager.user_info == response_data["data"]["user"]
            assert cookie_manager.is_valid
            assert cookie_manager.last_check_time is not None


def test_check_validity_request_error(cookie_manager):
    """测试cookie有效性检查请求错误"""
    with patch("requests.Session.get", side_effect=requests.RequestException("Network error")):
        valid, error = cookie_manager.check_validity()
        assert not valid
        assert "Network error" in error
        assert not cookie_manager.is_valid


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
    new_cookie = next((c for c in cookie_manager.cookies if c["name"] == "new_cookie"), None)
    assert new_cookie is not None
    assert new_cookie["value"] == "new_value"
    assert new_cookie["domain"] == ".weibo.com"
    assert new_cookie["path"] == "/"
    assert new_cookie["secure"] is True
    assert new_cookie["httpOnly"] is True
    assert new_cookie["sameSite"] == "None"  # secure为True时，sameSite应为None


def test_get_session_valid(cookie_manager):
    """测试获取有效会话"""
    cookie_manager.is_valid = True
    session = cookie_manager.get_session()
    assert session == cookie_manager._session


def test_get_session_invalid(cookie_manager):
    """测试获取无效会话"""
    cookie_manager.is_valid = False
    assert cookie_manager.get_session() is None


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
    
    with patch("requests.Session.get", return_value=mock_response):
        status = cookie_manager.get_status()
        assert status["is_valid"]
        assert "test_user" in status["user_info"]["screen_name"]
