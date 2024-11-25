from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
import json
import time
import traceback

def get_weibo_cookies():
    driver = None
    try:
        print("正在初始化 Chrome 选项...")
        # 设置 Chrome 选项
        chrome_options = Options()
        chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        
        # 添加一些额外的选项来提高稳定性
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        
        print("正在启动浏览器...")
        # 初始化浏览器
        driver = webdriver.Chrome(options=chrome_options)
        
        print("正在访问微博登录页面...")
        # 访问微博登录页面
        driver.get('https://passport.weibo.com/sso/signin')
        
        print("等待登录...")
        print("请在浏览器中完成登录操作。")
        print("脚本会在检测到登录成功后自动继续。")
        
        # 等待登录成功（最多等待5分钟）
        max_wait_time = 300  # 5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # 获取当前 URL
            current_url = driver.current_url
            
            # 如果 URL 包含特定字符串，可能表示已登录
            if "passport.weibo.com" not in current_url and "login.sina.com" not in current_url:
                print("检测到可能已登录成功...")
                # 再等待几秒确保页面完全加载
                time.sleep(5)
                break
                
            time.sleep(2)  # 每2秒检查一次
        
        print("正在获取 cookies...")
        # 获取所有 cookies
        cookies = driver.get_cookies()
        
        print(f"成功获取到 {len(cookies)} 个 cookies")
        
        # 将 cookies 保存到文件
        with open('weibo_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print("Cookies 已保存到 weibo_cookies.json 文件中")
        return cookies
        
    except WebDriverException as e:
        print(f"WebDriver 错误: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return None
    except Exception as e:
        print(f"发生错误: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return None
    finally:
        if driver:
            try:
                print("正在关闭浏览器...")
                driver.quit()
            except Exception as e:
                print(f"关闭浏览器时发生错误: {str(e)}")

if __name__ == '__main__':
    print("开始运行脚本...")
    cookies = get_weibo_cookies()
    if cookies:
        print("脚本执行成功!")
    else:
        print("脚本执行失败!")
