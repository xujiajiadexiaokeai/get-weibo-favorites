"""认证模块，处理微博登录和cookie管理"""
import json
import os
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .. import config
from ..utils import LogManager

# 设置日志记录器
logger = LogManager.setup_logger("auth")


class CookieManager:
    """Cookie管理器"""

    def __init__(self):
        """初始化Cookie管理器"""
        self.cookies: List[Dict] = []
        self.last_check_time: Optional[datetime] = None
        self.is_valid: bool = False
        self.user_info: Optional[Dict] = None
        self._session: Optional[requests.Session] = None
        self.load_cookies()

    def load_cookies(self) -> bool:
        """从文件加载cookies

        Returns:
            bool: 是否成功加载
        """
        try:
            with open(config.COOKIES_FILE, "r", encoding="utf-8") as f:
                self.cookies = json.load(f)
            self._create_session()
            return True
        except FileNotFoundError:
            logger.error("Cookie文件不存在，请先运行 auth.py 获取cookies")
            return False
        except json.JSONDecodeError:
            logger.error("Cookie文件格式错误")
            return False

    def save_cookies(self) -> bool:
        """保存cookies到文件

        Returns:
            bool: 是否成功保存
        """
        try:
            with open(config.COOKIES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cookies, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
            return False

    def _create_session(self):
        """创建请求会话"""
        self._session = requests.Session()
        
        # 设置cookies
        for cookie in self.cookies:
            self._session.cookies.set(cookie["name"], cookie["value"])

        # 设置请求头
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://weibo.com/fav",
            }
        )

    def check_validity(self) -> Tuple[bool, Optional[str]]:
        """检查cookie是否有效

        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if not self._session:
            return False, "会话未初始化"

        try:
            weibo_uid = os.getenv("WEIBO_UID") or ""
            # 使用用户信息接口检查cookie有效性
            response = self._session.get(
                f"https://weibo.com/ajax/profile/info?uid={weibo_uid}",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if "data" in data and "user" in data["data"]:
                self.is_valid = True
                self.user_info = data["data"]["user"]
                self.last_check_time = datetime.now()
                self._update_cookies_from_response(response)
                return True, None
            else:
                self.is_valid = False
                return False, "无法获取用户信息"

        except requests.RequestException as e:
            self.is_valid = False
            return False, f"请求失败: {str(e)}"

    def _update_cookies_from_response(self, response: requests.Response):
        """从响应中更新cookies

        Args:
            response: 响应对象
        """
        new_cookies = response.cookies.get_dict()
        if new_cookies:
            # 更新session中的cookies
            self._session.cookies.update(new_cookies)
            
            # 更新cookies列表
            for name, value in new_cookies.items():
                # 查找并更新已存在的cookie
                updated = False
                for cookie in self.cookies:
                    if cookie["name"] == name:
                        cookie["value"] = value
                        updated = True
                        break
                # 如果是新cookie，添加到列表
                if not updated:
                    # 从response.cookies中获取完整的cookie信息
                    cookie_obj = next(
                        (c for c in response.cookies if c.name == name),
                        None
                    )
                    if cookie_obj:
                        new_cookie = {
                            "name": name,
                            "value": value,
                            "domain": cookie_obj.domain or ".weibo.com",
                            "path": cookie_obj.path or "/",
                            "secure": cookie_obj.secure,
                            "httpOnly": cookie_obj.has_nonstandard_attr("HttpOnly"),
                            "sameSite": "None" if cookie_obj.secure else "Lax"
                        }
                        # 添加过期时间（如果有）
                        if cookie_obj.expires:
                            new_cookie["expiry"] = cookie_obj.expires
                        self.cookies.append(new_cookie)
                    else:
                        # 如果无法获取完整信息，使用默认值
                        self.cookies.append({
                            "name": name,
                            "value": value,
                            "domain": ".weibo.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": True,
                            "sameSite": "None"
                        })
            
            # 保存更新后的cookies
            self.save_cookies()

    def get_session(self) -> Optional[requests.Session]:
        """获取当前会话

        Returns:
            Optional[requests.Session]: 会话对象
        """
        return self._session if self.is_valid else None

    def get_status(self) -> Dict:
        """获取cookie状态信息

        Returns:
            Dict: 状态信息
        """
        # 如果超过5分钟没有检查，重新检查有效性
        if (not self.last_check_time or 
            datetime.now() - self.last_check_time > timedelta(minutes=5)):
            self.check_validity()
        
        return {
            "is_valid": self.is_valid,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "user_info": self.user_info,
            "cookies_count": len(self.cookies)
        }


def get_weibo_cookies() -> List[Dict]:
    """获取微博 cookies

    Returns:
        List[Dict]: cookies列表
    """
    driver = None
    try:
        logger.info("正在初始化 Chrome 选项...")
        # 设置 Chrome 选项
        chrome_options = Options()
        chrome_options.binary_location = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )

        # 添加一些额外的选项来提高稳定性
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        logger.info("正在启动浏览器...")
        # 初始化浏览器
        driver = webdriver.Chrome(options=chrome_options)

        logger.info("正在访问微博登录页面...")
        # 访问微博登录页面
        driver.get("https://passport.weibo.com/sso/signin")

        logger.info("等待登录...")
        logger.info("请在浏览器中完成登录操作。")
        logger.info("脚本会在检测到登录成功后自动继续。")

        # 等待登录成功（最多等待5分钟）
        max_wait_time = 300  # 5分钟
        start_time = time.time()
        logged_in = False

        while time.time() - start_time < max_wait_time:
            try:
                # 获取当前 URL
                current_url = driver.current_url

                # 如果 URL 包含特定字符串，可能表示已登录
                if (
                    "passport.weibo.com" not in current_url
                    and "login.sina.com" not in current_url
                ):
                    logger.info("检测到可能已登录成功...")
                # 再等待几秒确保页面完全加载
                time.sleep(5)
                logged_in = True
                break

                # TODO: 检查是否已经跳转到登录成功页面
                # if "weibo.com" in driver.current_url and "passport.weibo" not in driver.current_url:
                #     logged_in = True
                #     break
            except WebDriverException:
                pass
            time.sleep(1)

        if not logged_in:
            raise Exception("登录超时")

        logger.info("登录成功，正在获取cookies...")
        # 获取所有cookies
        cookies = driver.get_cookies()

        # 保存cookies到文件
        with open(config.COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        logger.info(f"已保存 {len(cookies)} 个cookies到文件")
        return cookies

    except Exception as e:
        logger.error(f"获取cookies失败: {e}")
        logger.error(traceback.format_exc())
        raise

    finally:
        if driver:
            driver.quit()


def get_session() -> Optional[requests.Session]:
    """获取有效的会话对象

    Returns:
        Optional[requests.Session]: 会话对象，如果cookie无效则返回None
    """
    return cookie_manager.get_session()

def get_cookie_status() -> Dict:
    """获取cookie状态信息

    Returns:
        Dict: 状态信息
    """
    return cookie_manager.get_status()


if __name__ == "__main__":
    logger.info("开始运行脚本...")
    cookies = get_weibo_cookies()
    if cookies:
        # 初始化CookieManager并验证
        cookie_manager = CookieManager()
        valid, error = cookie_manager.check_validity()
        if valid:
            logger.info("Cookie验证成功！")
            status = cookie_manager.get_status()
            logger.info(f"用户信息: {status['user_info']['screen_name']}")
        else:
            logger.error(f"Cookie验证失败: {error}")
