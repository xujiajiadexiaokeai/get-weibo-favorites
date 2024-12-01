# weibo_crawler.py

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from time import sleep
import traceback

import requests
from requests.exceptions import RequestException

from . import config
from .utils import setup_logger
from .auth import load_cookies, create_session
from .database import save_weibo

# 设置日志记录器
logger = setup_logger()

def get_favorites(session: requests.Session, page: int = 1) -> List[Dict]:
    """获取指定页的收藏列表
    
    Args:
        session: 请求会话
        page: 页码
        
    Returns:
        收藏列表
    """
    try:
        response = session.get(
            config.BASE_URL,
            params={"page": page}
        )
        response.raise_for_status()
        data = response.json()
        
        favorites = data.get("data", [])
        if not favorites:
            logger.info("没有更多数据了")
        return favorites
        
    except Exception as e:
        logger.error(f"获取第 {page} 页数据失败: {str(e)}")
        return []

def load_crawler_state() -> dict:
    """加载爬虫状态
    
    Returns:
        包含上次爬取状态的字典
    """
    try:
        with open(config.CRAWLER_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_id": None, "last_crawl_time": None}

def save_crawler_state(state: dict):
    """保存爬虫状态
    
    Args:
        state: 包含爬取状态的字典
    """

    # TODO: 日志记录本次爬取状态
    with open(config.CRAWLER_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def crawl_favorites(cookies: List[Dict], page_number: int = 0) -> List[Dict]:
    """爬取微博收藏
    
    Args:
        cookies: cookies列表
        page_number: 要爬取的页数，0表示爬取所有页或直到重复内容为止
        
    Returns:
        收藏列表
    """
    all_favorites = []
    empty_weibos = []  # 用于存储空文本的微博
    page = 1
    
    # TODO: 测试时不更新状态或者另外保存?
    # 加载上次爬取状态
    state = load_crawler_state()
    last_id = state.get("last_id")
    
    # 初始化session
    session = create_session(cookies)

    try:
        while True:
            logger.info(f"正在爬取第 {page} 页...")
            
            # 获取收藏列表
            favorites = get_favorites(session, page)
            if not favorites:
                logger.info("没有更多收藏了")
                break
            # 检查是否遇到重复内容
            found_duplicate = False
            # 遍历收藏列表
            for item in favorites:
                weibo = parse_weibo(item)
                # 检查是否遇到已爬取的内容
                found_duplicate = check_duplicate(last_id, weibo['id'])
                if found_duplicate:
                    break
                
                # 检查文本是否为空
                if check_empty_text(weibo):
                    empty_weibos.append({
                        "id": weibo["id"],
                        "url": weibo["url"]
                    })
                else:
                    all_favorites.append(weibo)
            
            if found_duplicate:
                break
            
            if page_number != 0 and page >= page_number:
                break
            
            page += 1
            sleep(config.REQUEST_DELAY)
    
    except Exception as e:
        logger.error(f"爬取过程出错: {str(e)}")
    
    finally:
        session.close()
        
        # 输出统计信息
        # 如果有新数据，更新状态并保存
        if all_favorites:
            # 更新爬虫状态
            new_state = {
                "last_id": all_favorites[0]['id'],  # 第一条是最新的
                "last_crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_crawler_state(new_state)
            logger.info(f"成功获取 {len(all_favorites)} 条有效收藏")

            # 保存爬取结果all_favorites
            with open(config.FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_favorites, f, ensure_ascii=False, indent=2)
            logger.info("数据已保存到 favorites.json")

        if empty_weibos:
            logger.warning(f"发现 {len(empty_weibos)} 条空文本微博:")
            for weibo in empty_weibos:
                logger.warning(f"  - ID: {weibo['id']}, URL: {weibo['url']}")
    
    return all_favorites

def check_duplicate(last_id: str, weibo_id: str) -> bool:
    """检查微博是否已存在
    
    Args:
        last_id: 上次爬取的微博ID
        weibo_id: 微博ID
    
    Returns:
        True 已存在，False 不存在
    """
     # 如果遇到已爬取的微博ID，停止爬取
    if last_id and weibo_id == last_id:
        logger.info(f"遇到已爬取的微博(ID: {last_id})，停止爬取")
        return True
    else:
        return False

def check_empty_text(weibo: Dict) -> bool:
    """检查微博文本是否为空
    
    Args:
        weibo: 微博数据
    
    Returns:
        True 空文本，False 非空文本
    """
    if not weibo.get("text", "").strip():
        logger.warning(f"发现空文本微博 - ID: {weibo['id']}, URL: {weibo['url']}")
        return True
    else:
        return False


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
        
        return weibo
    except Exception as e:
        logger.error(f"解析微博数据时出错: {str(e)}")
        return {
            "id": str(data.get("idstr", "")),
            "error": f"解析错误: {str(e)}",
            "raw_data": data
        }

def main():
    """主函数"""
    try:
        # 加载cookies
        cookies = load_cookies()
        if not cookies:
            logger.error("无法加载cookies，请先运行 get_weibo_cookies.py 获取cookies")
            return
        
        # 获取收藏数据
        favorites = crawl_favorites(cookies)
        # 保存到数据库
        try:
            save_weibo(favorites)
        except Exception as e:
            logger.error(f"保存到数据库失败: {str(e)}")
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main()