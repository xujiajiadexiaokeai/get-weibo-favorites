"""任务处理模块"""

import json
import requests
from datetime import datetime
from typing import Dict, Any, Tuple

from ..database import (
    update_weibo_content,
    save_image_metadata,
    update_image_process_result,
    update_image_process_status,
)
from ..utils import LogManager
from .auth import CookieManager
from .media_processor import process_image

logger = LogManager.setup_logger("task")


class LongTextError(Exception):
    """长文本处理相关错误的基类"""
    def __init__(self, message: str, weibo_id: str):
        super().__init__(message)
        self.weibo_id = weibo_id


class CookieValidationError(LongTextError):
    """Cookie验证失败的错误"""
    pass


class ParameterError(LongTextError):
    """参数验证失败的错误"""
    pass


class TextFetchError(LongTextError):
    """获取长文本失败的错误"""
    pass


class TextExtractError(LongTextError):
    """提取长文本失败的错误"""
    pass


class TextSaveError(LongTextError):
    """保存长文本失败的错误"""
    pass


class LongTextTaskProcessor:
    """长文本任务处理器"""

    def __init__(self):
        self.cookie_manager = CookieManager()

    def _validate_cookie(self, weibo_id: str) -> None:
        """验证Cookie

        Args:
            weibo_id: 微博ID

        Raises:
            CookieValidationError: Cookie验证失败
        """
        valid, error = self.cookie_manager.check_validity()
        if not valid:
            logger.error(f"Cookie验证失败：{error}, fetch_long_text任务中止")
            raise CookieValidationError(error, weibo_id)

    def _validate_parameters(self, task_data: Dict[str, Any]) -> Tuple[str, str]:
        """验证任务参数

        Args:
            task_data: 任务数据

        Returns:
            Tuple[str, str]: weibo_id 和 url

        Raises:
            ParameterError: 参数验证失败
        """
        weibo_id = task_data["weibo_id"]
        url = task_data.get("url")
        if not url:
            logger.error(f"微博 {weibo_id} 缺少URL")
            raise ParameterError("缺少URL", weibo_id)
        return weibo_id, url

    def _fetch_long_text(self, weibo_id: str, url: str) -> Dict:
        """获取长文本

        Args:
            weibo_id: 微博ID
            url: API URL

        Returns:
            Dict: API响应数据

        Raises:
            TextFetchError: 获取长文本失败
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://weibo.com/u/page/fav/" + weibo_id,
                "Cookie": ";".join(
                    [f"{cookie['name']}={cookie['value']}" for cookie in self.cookie_manager.cookies]
                ),
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            logger.debug(f"获取微博完整长文本成功: {weibo_id}")
            return response.json()
        except requests.RequestException as e:
            raise TextFetchError(f"请求失败: {str(e)}", weibo_id) from e

    def _extract_long_text(self, data: Dict, weibo_id: str) -> str:
        """从响应数据中提取长文本

        Args:
            data: API响应数据
            weibo_id: 微博ID

        Returns:
            str: 提取到的长文本

        Raises:
            TextExtractError: 提取长文本失败
        """
        logger.debug(f"提取到的数据：{data.get('data')}")
        long_text = data.get("data", {}).get("longTextContent")
        if not long_text:
            raise TextExtractError(f"未能从响应中提取到完整内容", weibo_id)
        return long_text

    def _save_long_text(self, weibo_id: str, long_text: str) -> str:
        """保存长文本

        Args:
            weibo_id: 微博ID
            long_text: 长文本内容

        Returns:
            str: 当前时间

        Raises:
            TextSaveError: 保存长文本失败
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_data = {
                "long_text": long_text,
                "text_length": len(long_text),
                "crawled": True,
                "crawl_status": "completed",
                "updated_at": current_time,
            }

            update_weibo_content(weibo_id, update_data)
            logger.debug(f"成功获取并更新微博完整内容: {weibo_id}")
            return current_time
        except Exception as e:
            raise TextSaveError(f"保存长文本失败: {str(e)}", weibo_id) from e

    def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理长文本任务

        Args:
            task_data: 任务数据，包含微博ID和URL等信息

        Returns:
            dict: 处理结果，包含以下字段：
                - success: 是否成功
                - weibo_id: 微博ID
                - content: 长文本内容（如果成功）
                - processed_at: 处理时间（如果成功）
                - error: 错误信息（如果失败）
        """
        try:
            # 第一步：验证Cookie
            weibo_id = task_data["weibo_id"]
            self._validate_cookie(weibo_id)

            # 第二步：验证参数
            weibo_id, url = self._validate_parameters(task_data)

            # 第三步：获取长文本
            response_data = self._fetch_long_text(weibo_id, url)

            # 第四步：提取长文本
            long_text = self._extract_long_text(response_data, weibo_id)

            # 第五步：保存长文本
            current_time = self._save_long_text(weibo_id, long_text)

            return {
                "success": True,
                "weibo_id": weibo_id,
                "content": long_text,
                "processed_at": current_time,
            }

        except (CookieValidationError, ParameterError, TextFetchError, 
                TextExtractError, TextSaveError) as e:
            logger.error(str(e))
            return {
                "success": False,
                "weibo_id": e.weibo_id,
                "error": str(e)
            }
        except Exception as e:
            error_msg = f"处理长文本时发生未知错误: {str(e)}"
            logger.error(f"{error_msg}, task_data: {task_data}")
            return {
                "success": False,
                "weibo_id": task_data["weibo_id"],
                "error": error_msg
            }


class ImageProcessError(Exception):
    """图片处理相关错误的基类"""
    def __init__(self, message: str, weibo_id: str, pic_id: str):
        super().__init__(message)
        self.weibo_id = weibo_id
        self.pic_id = pic_id


class ImageMetadataSaveError(ImageProcessError):
    """保存图片元数据时的错误"""
    pass


class ImageDownloadError(ImageProcessError):
    """下载图片时的错误"""
    pass


class ImageProcessingError(ImageProcessError):
    """图片处理时的错误"""
    pass


class ImageStatusUpdateError(ImageProcessError):
    """更新图片处理状态时的错误"""
    pass




class ImageTaskProcessor:
    """图片任务处理器"""

    def _update_image_status(self, weibo_id: str, pic_id: str, error_msg: str):
        """更新图片处理状态

        Args:
            weibo_id: 微博ID
            pic_id: 图片ID
            error_msg: 错误信息
        """
        try:
            update_image_process_status(weibo_id, pic_id, error_msg)
        except Exception as e:
            raise ImageStatusUpdateError(
                f"更新图片处理状态失败: {str(e)}", 
                weibo_id, 
                pic_id
            ) from e

    def _fetch_image_content(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取图片内容

        Args:
            task_data: 任务数据，包含以下字段：
                - url: 图片URL
                - width: 图片宽度
                - height: 图片高度

        Returns:
            dict: image_content, 包含以下字段：
                - type: 图片类型
                - content: 图片Data URL字符串

        Raises:
            ImageDownloadError: 下载图片失败时抛出
        """
        try:
            # 准备请求头
            headers = {
                "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ru;q=0.6",
                "priority": "i",
                "referer": "https://weibo.com/",
                "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"macOS\"",
                "sec-fetch-dest": "image",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-site": "cross-site",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }

            # 发送请求
            response = requests.get(task_data["url"], headers=headers, timeout=30)
            response.raise_for_status()

            # 验证内容类型
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith('image/'):
                raise ImageDownloadError(
                    f"Unexpected content type: {content_type}",
                    task_data["weibo_id"],
                    task_data["pic_id"]
                )

            # 读取图片内容
            content = response.content
            return {"type": content_type, "content": content}

        except requests.RequestException as e:
            raise ImageDownloadError(
                f"Failed to download image: {str(e)}", 
                task_data["weibo_id"], 
                task_data["pic_id"]
            ) from e

    def _save_image_metadata(self, image_data: Dict[str, Any]):
        """保存图片元数据

        Args:
            image_data: 图片数据
        """
        try:
            save_image_metadata(image_data)
        except Exception as e:
            raise ImageMetadataSaveError(
                str(e), 
                image_data["weibo_id"], 
                image_data["pic_id"]
            ) from e

    def _process_and_save_image(self, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理图片并保存结果

        Args:
            image_data: 图片数据

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 直接使用二进制内容，不需要解码
            processed_images = process_image(image_data["content"])
            update_image_process_result(
                image_data["weibo_id"],
                image_data["pic_id"],
                processed_images
            )
            return {
                "success": True,
                "weibo_id": image_data["weibo_id"],
                "pic_id": image_data["pic_id"]
            }
        except Exception as e:
            # 先尝试更新状态
            try:
                self._update_image_status(
                    image_data["weibo_id"],
                    image_data["pic_id"],
                    str(e)
                )
            except ImageStatusUpdateError as status_error:
                logger.error(str(status_error))

            # 抛出处理错误
            raise ImageProcessingError(
                f"处理图片失败: {str(e)}", 
                image_data["weibo_id"], 
                image_data["pic_id"]
            ) from e

    def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理图片内容，包括获取和处理两个步骤

        Args:
            task_data: 任务数据，包含以下字段：
                - weibo_id: 微博ID
                - pic_id: 图片ID
                - url: 图片URL
                - width: 图片宽度
                - height: 图片高度

        Returns:
            dict: 处理结果，包含以下字段：
                - success: 是否成功
                - weibo_id: 微博ID
                - pic_id: 图片ID
                - error: 错误信息（如果失败）
        """
        try:
            # 第一步：获取图片内容
            image_content = self._fetch_image_content(task_data)

            # 第二步：保存图片元数据
            # 构建图片数据
            image_data = {
                "weibo_id": task_data["weibo_id"],
                "pic_id": task_data["pic_id"],
                "url": task_data["url"],
                "width": task_data.get("width"),
                "height": task_data.get("height"),
                "content_type": image_content["type"],
                "content": image_content["content"]
            }

            # 保存图片元数据
            self._save_image_metadata(image_data)

            # 第三步：处理图片并保存
            process_result = self._process_and_save_image(image_data)
            return process_result

        except ImageMetadataSaveError as e:
            logger.error(f"保存图片元数据失败: {e}")
            return {
                "success": False,
                "weibo_id": e.weibo_id,
                "pic_id": e.pic_id,
                "error": str(e)
            }
        except ImageDownloadError as e:
            logger.error(f"下载图片失败: {e}")
            return {
                "success": False,
                "weibo_id": e.weibo_id,
                "pic_id": e.pic_id,
                "error": str(e)
            }
        except ImageProcessingError as e:
            logger.error(str(e))
            return {
                "success": False,
                "weibo_id": e.weibo_id,
                "pic_id": e.pic_id,
                "error": str(e)
            }
        except Exception as e:
            error_msg = f"处理图片时发生未知错误: {str(e)}"
            logger.error(f"{error_msg}, task_data: {task_data}")
            return {
                "success": False,
                "weibo_id": task_data["weibo_id"],
                "pic_id": task_data["pic_id"],
                "error": error_msg
            }


# 创建处理器实例
long_text_task_processor = LongTextTaskProcessor()
image_task_processor = ImageTaskProcessor()


def process_image_content(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理图片内容的入口函数"""
    return image_task_processor.process(task_data)


def fetch_long_text(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """获取长文本的入口函数"""
    return long_text_task_processor.process(task_data)
