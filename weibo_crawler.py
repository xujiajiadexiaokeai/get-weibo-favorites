# weibo_crawler.py

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from time import sleep

import requests
from requests.exceptions import RequestException

from utils import setup_logger
from weibo_auth import load_cookies, create_session

# 设置日志记录器
logger = setup_logger()

BASE_URL = "https://weibo.com/ajax/favorites/all_fav"
REQUEST_DELAY = 2  # 请求间隔秒数

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
            BASE_URL,
            params={"page": page}
        )
        response.raise_for_status()
        data = response.json()
        
        # 打印响应数据结构
        logger.info(f"API响应数据结构: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        favorites = data.get("data", [])
        if not favorites:
            logger.info("没有更多数据了")
        return favorites
        
    except Exception as e:
        logger.error(f"获取第 {page} 页数据失败: {str(e)}")
        return []

def crawl_favorites(cookies: List[Dict], page_number: int = 0) -> List[Dict]:
    """爬取微博收藏
    
    Args:
        cookies: cookies列表
        page_number: 要爬取的页数，0表示爬取所有页
        
    Returns:
        收藏列表
    """
    session = create_session(cookies)
    all_favorites = []
    empty_weibos = []  # 用于存储空文本的微博
    page = 1
    
    try:
        while True:
            logger.info(f"正在获取第 {page} 页")
            
            favorites = get_favorites(session, page)
            if not favorites:
                break
                
            # 如果是第一页，打印第一条数据的结构
            if page == 1:
                logger.info("第一页第一条数据结构:")
                logger.info(json.dumps(favorites[0], ensure_ascii=False, indent=2))
            
            for item in favorites:
                weibo = parse_weibo(item)
                
                # 检查文本是否为空
                if not weibo.get("text", "").strip():
                    empty_weibos.append({
                        "id": weibo["id"],
                        "url": weibo["url"]
                    })
                    logger.warning(f"发现空文本微博 - ID: {weibo['id']}, URL: {weibo['url']}")
                else:
                    all_favorites.append(weibo)
                    # 保存到数据库
                    try:
                        # save_weibo(weibo)
                        pass
                    except Exception as e:
                        logger.error(f"保存到数据库失败: {str(e)}")
            
            # 保存到文件
            with open("favorites.json", "w", encoding="utf-8") as f:
                json.dump(all_favorites, f, ensure_ascii=False, indent=2)
            
            if page_number != 0 and page >= page_number:
                break
            
            page += 1
            sleep(REQUEST_DELAY)
    
    except Exception as e:
        logger.error(f"爬取过程出错: {str(e)}")
    
    finally:
        session.close()
        
        # 输出统计信息
        logger.info(f"成功获取 {len(all_favorites)} 条有效收藏")
        if empty_weibos:
            logger.warning(f"发现 {len(empty_weibos)} 条空文本微博:")
            for weibo in empty_weibos:
                logger.warning(f"  - ID: {weibo['id']}, URL: {weibo['url']}")
        
        logger.info("数据已保存到 favorites.json")
    
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
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main()