"""
队列任务处理模块
"""

import json
from datetime import datetime

import requests

from .. import config
from ..database import update_weibo_content
from ..utils import LogManager
from .auth import CookieManager

logger = LogManager.setup_logger("task")


def extract_long_text(data):
    logger.info(f"提取到的数据：{data.get('data')}")
    longTextContent = data.get("data").get("longTextContent")
    if longTextContent:
        return longTextContent
    else:
        return None


def fetch_long_text(task_data):
    """获取微博长文本的完整内容

    Args:
        task_data (dict): 任务数据，包含微博ID和URL等信息

    Returns:
        dict: 处理结果
    """
    cookie_manager = CookieManager()
    valid, error = cookie_manager.check_validity()
    if valid:
        cookies = cookie_manager.cookies
    else:
        logger.error(f"Cookie验证失败：{error},fetch_long_text任务中止")
        return {"success": False, "weibo_id": task_data["weibo_id"], "error": error}

    weibo_id = task_data["weibo_id"]
    url = task_data.get("url")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/u/page/fav/" + weibo_id,
        "Cookie": ";".join(
            [f"{cookie['name']}={cookie['value']}" for cookie in cookies]
        ),
    }
    if not url:
        logger.error(f"微博 {weibo_id} 缺少URL")
        return {"success": False, "weibo_id": weibo_id, "error": "Missing URL"}

    logger.info(f"开始获取微博完整长文本: {weibo_id}")

    try:
        # 发送请求获取完整长文本
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        # # 解析响应内容
        long_text = extract_long_text(data)
        if not long_text:
            logger.warning(f"未能从响应中提取到完整内容: {weibo_id}")
            return {
                "success": False,
                "weibo_id": weibo_id,
                "error": "Failed to extract content",
            }

        # 更新数据库中的内容
        update_data = {
            "long_text": long_text,
            "text_length": len(long_text),
            "crawled": True,
            "crawl_status": "completed",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        update_weibo_content(weibo_id, update_data)
        with open(config.DATA_DIR / "long_text.json", "w", encoding="utf-8") as f:
            json.dump(update_data, f, ensure_ascii=False, indent=2)
        logger.info("数据已保存到 long_text.json")
        logger.info(f"成功获取并更新微博完整内容: {weibo_id}")
        return {
            "success": True,
            "weibo_id": weibo_id,
            "content": long_text,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except requests.RequestException as e:
        error_msg = f"请求失败 {weibo_id}: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "weibo_id": weibo_id, "error": error_msg}
    except Exception as e:
        error_msg = f"处理失败 {weibo_id}: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "weibo_id": weibo_id, "error": error_msg}
