from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
import json
import time
import traceback
from typing import List, Dict
import requests

from . import config
from .utils import setup_logger

# 设置日志记录器
logger = setup_logger(
    "auth",
    )

def load_cookies() -> List[Dict]:
    """从文件加载cookies
    
    Returns:
        cookies列表
    """
    try:
        with open(config.COOKIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Cookie文件不存在，请先运行 weibo_auth.py 获取cookies")
        raise
    except json.JSONDecodeError:
        logger.error("Cookie文件格式错误")
        raise

def create_session(cookies: List[Dict]) -> requests.Session:
    """创建请求会话
    
    Args:
        cookies: cookies列表
        
    Returns:
        配置好的会话对象
    """
    session = requests.Session()
    
    # 设置cookies
    for cookie in cookies:
        session.cookies.set(cookie["name"], cookie["value"])
    
    # 设置请求头
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://weibo.com/fav',
    })
    
    return session

def get_weibo_cookies():
    """获取微博 cookies
    
    Returns:
        cookies列表
    """
    driver = None
    try:
        logger.info("正在初始化 Chrome 选项...")
        # 设置 Chrome 选项
        chrome_options = Options()
        chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        
        # 添加一些额外的选项来提高稳定性
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        logger.info("正在启动浏览器...")
        # 初始化浏览器
        driver = webdriver.Chrome(options=chrome_options)
        
        logger.info("正在访问微博登录页面...")
        # 访问微博登录页面
        driver.get('https://passport.weibo.com/sso/signin')
        
        logger.info("等待登录...")
        logger.info("请在浏览器中完成登录操作。")
        logger.info("脚本会在检测到登录成功后自动继续。")
        
        # 等待登录成功（最多等待5分钟）
        max_wait_time = 300  # 5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # 获取当前 URL
            current_url = driver.current_url
            
            # 如果 URL 包含特定字符串，可能表示已登录
            if "passport.weibo.com" not in current_url and "login.sina.com" not in current_url:
                logger.info("检测到可能已登录成功...")
                # 再等待几秒确保页面完全加载
                time.sleep(5)
                break
                
            time.sleep(2)  # 每2秒检查一次
        
        logger.info("正在获取 cookies...")
        # 获取所有 cookies
        cookies = driver.get_cookies()
        
        # 保存cookies到文件
        with open(config.COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        logger.info("成功保存cookies")
        return cookies
        
    except WebDriverException as e:
        logger.error(f"WebDriver 错误: {str(e)}")
        logger.error("详细错误信息:")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        logger.error("详细错误信息:")
        logger.error(traceback.format_exc())
        return None
    finally:
        if driver:
            try:
                logger.info("正在关闭浏览器...")
                driver.quit()
            except Exception as e:
                logger.error(f"关闭浏览器时发生错误: {str(e)}")

if __name__ == '__main__':
    logger.info("开始运行脚本...")
    cookies = get_weibo_cookies()
    if cookies:
        logger.info("脚本执行成功!")
    else:
        logger.error("脚本执行失败!")
