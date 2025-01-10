"""爬虫模块，负责爬取和解析微博收藏"""
import json
import traceback
from datetime import datetime
from time import sleep
from typing import Dict, List

import requests

from .. import config
from ..database import save_weibo
from ..utils import LogManager
from .queue import ImageProcessQueue, LongTextProcessQueue

# 设置日志记录器
logger = LogManager.setup_logger("crawler")


def get_favorites(session: requests.Session, page: int = 1) -> List[Dict]:
    """获取指定页的收藏列表

    Args:
        session: 请求会话
        page: 页码

    Returns:
        收藏列表
    """
    try:
        response = session.get(config.BASE_URL, params={"page": page})
        response.raise_for_status()
        data = response.json()

        favorites = data.get("data", [])
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
        with open(config.CRAWLER_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_id": None, "last_crawl_time": None}


def save_crawler_state(state: dict):
    """保存爬虫状态

    Args:
        state: 包含爬取状态的字典
    """

    # TODO: 日志记录本次爬取状态
    with open(config.CRAWLER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def crawl_favorites(
    ltp_queue: LongTextProcessQueue,
    img_queue: ImageProcessQueue,
    session: requests.Session,
    page_number: int = 0,
) -> List[Dict]:
    """爬取微博收藏

    Args:
        ltp_queue: 长文本处理队列
        page_number: 要爬取的页数，0表示爬取所有页或直到重复内容为止

    Returns:
        收藏列表
    """
    all_favorites = []
    page = 1

    # 加载上次爬取状态
    state = load_crawler_state()
    last_id = state.get("last_id")

    try:
        while True:
            logger.info(f"正在爬取第 {page} 页...")

            # 获取收藏列表
            favorites = get_favorites(session, page)
            if not favorites and page == 1:
                logger.error("未获取到任何收藏数据，请检查cookies是否正确")
                break
            elif not favorites:
                logger.info("没有更多收藏了")
                break

            # 检查是否遇到重复内容
            found_duplicate = False
            # 遍历收藏列表
            for item in favorites:
                weibo = parse_weibo(item)  # 解析item
                # 检查是否遇到已爬取的内容
                found_duplicate = check_duplicate(last_id, weibo["id"])
                if found_duplicate:
                    break

                # 如果是长文本，添加到队列
                if weibo["is_long_text"]:
                    try:
                        job_id = ltp_queue.add_task(weibo)
                        logger.info(f"已将长文本微博添加到队列，ID: {weibo['id']}, Job ID: {job_id}")
                    except Exception as e:
                        logger.error(f"添加长文本任务失败: {e}")

                # 如果有图片，添加到队列
                if len(weibo["pic_ids"]) > 0:
                    try:
                        job_id = img_queue.add_task(weibo)
                        logger.info(f"已将图片微博添加到队列，ID: {weibo['id']}, Job ID: {job_id}")
                    except Exception as e:
                        logger.error(f"添加图片任务失败: {e}")

                all_favorites.append(weibo)
                # 保存到数据库
                save_weibo(weibo)

            if found_duplicate:
                break

            if page_number != 0 and page >= page_number:
                break

            page += 1
            sleep(config.REQUEST_DELAY)

    except Exception as e:
        logger.error(f"爬取过程出错: {str(e)}")
        logger.error(traceback.format_exc())

    finally:
        if session is not None:
            session.close()

        # 如果有新数据，更新状态
        if all_favorites:
            # 更新爬虫状态
            new_state = {
                "last_id": all_favorites[0]["id"],  # 第一条是最新的
                "last_crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_crawler_state(new_state)
            logger.info(f"成功获取 {len(all_favorites)} 条有效收藏")

            # 保存爬取结果all_favorites
            with open(config.FAVORITES_FILE, "w", encoding="utf-8") as f:
                json.dump(all_favorites, f, ensure_ascii=False, indent=2)
            logger.info("数据已保存到 favorites.json")

            # TODO: 爬虫不需要关心队列状态，由调度器管理
            # 输出队列状态
            queue_status = ltp_queue.get_queue_status()
            if queue_status:
                logger.info(f"队列状态: {queue_status}")

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


def parse_weibo_time(time_str: str) -> str:
    """将微博时间格式转换为标准ISO格式"""
    try:
        # 解析微博时间格式，例如："Sun Dec 01 12:09:53 +0800 2024"
        dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        # 转换为ISO格式
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"Failed to parse time string: {time_str}, Error: {e}")
        return time_str


def parse_weibo(data: Dict) -> Dict:
    """解析微博数据

    Args:
        data: 原始微博数据

    Returns:
        解析后的微博数据
    """

    def safe_str(value) -> str:
        """安全地将值转换为字符串，None转换为空字符串"""
        return str(value) if value is not None else ""

    try:
        user = data.get("user", {}) or {}  # 确保user是字典

        # 提取附加链接，如果url_struct不存在或为空，则返回空列表
        links = []
        url_structs = data.get("url_struct", [])
        if url_structs and isinstance(url_structs, list):
            for u in url_structs:
                if isinstance(u, dict) and "long_url" in u:
                    links.append(u["long_url"])
        # 如果存在mix_media_info，将图片提取出来塞入pic_infos中
        if "mix_media_info" in data and "items" in data["mix_media_info"]:
            pic_infos = {}
            for item in data["mix_media_info"]["items"]:
                if item.get("type") == "pic" and "data" in item:
                    pic_data = item["data"]
                    pic_id = pic_data.get("pic_id")
                    if pic_id:
                        pic_infos[pic_id] = pic_data
            if pic_infos:
                data["pic_infos"] = pic_infos

        weibo = {
            "id": safe_str(data.get("idstr")),
            "mblogid": safe_str(data.get("mblogid")),
            "created_at": parse_weibo_time(data.get("created_at", "")),
            "url": f"https://weibo.com/{safe_str(user.get('idstr'))}/{safe_str(data.get('mblogid'))}"
            if user
            else "",
            "user_name": safe_str(user.get("screen_name")),
            "user_id": safe_str(user.get("idstr")),
            "is_long_text": data.get("isLongText", False),
            "text": safe_str(data.get("text_raw")),  # 使用 text_raw 而不是 text
            "text_html": safe_str(data.get("text")),  # HTML 格式的文本
            "long_text": "",  # 需要后续从其他接口获取
            "source": safe_str(data.get("source")),
            "links": links,
            "pic_ids": data.get("pic_ids", []),  # 添加图片ID列表
            "pic_infos": data.get("pic_infos", {}),  # 添加原始图片信息
            "pic_num": data.get("pic_num", 0),  # 添加图片数量
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "crawled": False,  # 标记是否已经爬取了完整内容
            "crawl_status": "pending"
            if data.get("isLongText", False)
            else "completed",  # 爬取状态
        }

        return weibo
    except Exception as e:
        logger.error(f"解析微博数据时出错: {str(e)}")
        return {
            "id": safe_str(data.get("idstr")),
            "error": f"解析错误: {str(e)}",
            "raw_data": data,
        }

"""不再支持爬虫独立运行，转由调度器调度运行"""
