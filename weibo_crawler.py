# weibo_crawler.py

import requests
import json
import time
import logging
from typing import Dict, List, Optional
from requests.exceptions import RequestException
from datetime import datetime
from database import save_weibo, create_table

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://weibo.com/ajax/favorites/all_fav"
REQUEST_DELAY = 2  # 请求间隔秒数

def load_cookies() -> List[Dict]:
    """从文件加载cookies"""
    try:
        with open('weibo_cookies.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Cookie文件不存在，请先运行 get_weibo_cookies.py 获取cookies")
        raise
    except json.JSONDecodeError:
        logger.error("Cookie文件格式错误")
        raise

def create_session() -> requests.Session:
    """创建并配置requests会话"""
    session = requests.Session()
    cookies = load_cookies()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    
    # 设置请求头
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://weibo.com/fav',
    })
    
    return session

def get_weibo_fav(page_number: int = 0) -> List[Dict]:
    """获取微博收藏列表
    
    Args:
        page_number: 要获取的页数，0表示获取所有页
        
    Returns:
        收藏列表
    """
    session = create_session()
    all_favorites = []
    page = 1
    
    try:
        while True:
            logger.info(f"正在获取第 {page} 页")
            params = {
                'page': page,
                '_t': int(time.time() * 1000)  # 添加时间戳避免缓存
            }
            
            try:
                response = session.get(BASE_URL, params=params)
                response.raise_for_status()
                
                data = response.json()
                if not isinstance(data, dict):
                    logger.error(f"返回数据格式错误: {data}")
                    break
                
                favorites = data.get("data", [])
                if not favorites:
                    logger.info("没有更多数据了")
                    break
                
                # 如果是第一页，打印第一条数据的结构
                if page == 1:
                    logger.info("第一页第一条数据结构:")
                    logger.info(json.dumps(favorites[0], ensure_ascii=False, indent=2))
                
                parsed_favorites = [parse_weibo(item) for item in favorites]
                all_favorites.extend(parsed_favorites)
                
                if page_number != 0 and page >= page_number:
                    break
                
                page += 1
                time.sleep(REQUEST_DELAY)  # 添加请求延迟
                
            except RequestException as e:
                logger.error(f"请求错误: {str(e)}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {str(e)}")
                break
            except Exception as e:
                logger.error(f"未知错误: {str(e)}")
                break
    
    finally:
        session.close()
    
    return all_favorites

def parse_weibo(data: Dict) -> Dict:
    """解析微博数据
    
    Args:
        data: 原始微博数据
        
    Returns:
        解析后的微博数据
    """
    try:
        user = data.get("user", {})
        
        # 提取链接，如果url_struct不存在或为空，则返回空列表
        links = []
        url_structs = data.get("url_struct", [])
        if url_structs and isinstance(url_structs, list):
            for u in url_structs:
                if isinstance(u, dict) and "long_url" in u:
                    links.append(u["long_url"])
        
        weibo = {
            "id": str(data.get("idstr", "")),
            "created_at": data.get("created_at", ""),
            "url": f"https://weibo.com/{user.get('idstr', '')}/{data.get('mblogid', '')}" if user else "",
            "user_name": user.get("screen_name", ""),
            "user_id": str(user.get("idstr", "")),
            "is_long_text": data.get("isLongText", False),
            "text": data.get("text_raw", ""),  # 使用 text_raw 而不是 text
            "text_html": data.get("text", ""),  # HTML 格式的文本
            "source": data.get("source", ""),
            "links": links,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存到数据库
        try:
            save_weibo(weibo)
        except Exception as e:
            logger.error(f"保存到数据库失败: {str(e)}")
        
        return weibo
    except Exception as e:
        logger.error(f"解析微博数据时出错: {str(e)}")
        return {
            "id": str(data.get("idstr", "")),
            "error": f"解析错误: {str(e)}",
            "raw_data": data
        }

if __name__ == '__main__':
    try:
        # 初始化数据库表
        create_table()
        
        # 获取前5页数据作为测试
        favorites = get_weibo_fav(5)
        logger.info(f"成功获取 {len(favorites)} 条收藏")
        
        # 保存到文件
        with open('favorites.json', 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        logger.info("数据已保存到 favorites.json")
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")