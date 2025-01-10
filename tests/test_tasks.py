"""任务处理器测试模块"""

import json
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock, mock_open
from typing import Dict, Any

from weibo_favorites.crawler.tasks import (
    ImageTaskProcessor,
    ImageDownloadError,
    ImageMetadataSaveError,
    ImageProcessingError,
    ImageStatusUpdateError,
    LongTextTaskProcessor,
    CookieValidationError,
    ParameterError,
    TextFetchError,
    TextExtractError,
    TextSaveError,
)


@pytest.fixture
def image_task_processor():
    """创建图片任务处理器实例"""
    return ImageTaskProcessor()


@pytest.fixture
def mock_task_data():
    """模拟任务数据"""
    return {
        "weibo_id": "test_weibo_123",
        "pic_id": "test_pic_456",
        "url": "https://example.com/test.jpg",
        "width": 800,
        "height": 600,
    }


@pytest.fixture
def mock_image_data(mock_task_data):
    """模拟图片数据"""
    return {
        **mock_task_data,
        "content_type": "image/jpeg",
        "content": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/...",
    }


@pytest.fixture
def long_text_processor():
    """创建长文本任务处理器实例"""
    return LongTextTaskProcessor()


@pytest.fixture
def mock_long_text_data():
    """模拟长文本任务数据"""
    return {
        "weibo_id": "test_weibo_123",
        "url": "https://weibo.com/ajax/statuses/longtext?id=test_weibo_123"
    }


class TestImageTaskProcessor:
    """图片任务处理器测试类"""

    def test_update_image_status_success(self, image_task_processor, mock_task_data):
        """测试成功更新图片状态"""
        with patch("weibo_favorites.crawler.tasks.update_image_process_status", return_value=None) as mock_update:
            image_task_processor._update_image_status(
                mock_task_data["weibo_id"],
                mock_task_data["pic_id"],
                "test_error"
            )
            mock_update.assert_called_once_with(
                mock_task_data["weibo_id"],
                mock_task_data["pic_id"],
                "test_error"
            )

    def test_update_image_status_failure(self, image_task_processor, mock_task_data):
        """测试更新图片状态失败"""
        with patch("weibo_favorites.crawler.tasks.update_image_process_status") as mock_update:
            mock_update.side_effect = Exception("Database error")
            with pytest.raises(ImageStatusUpdateError) as exc_info:
                image_task_processor._update_image_status(
                    mock_task_data["weibo_id"],
                    mock_task_data["pic_id"],
                    "test_error"
                )
            assert "更新图片处理状态失败" in str(exc_info.value)

    def test_fetch_image_content_success(self, image_task_processor, mock_task_data):
        """测试成功获取图片内容"""
        mock_response = Mock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"fake_image_content"

        with patch("requests.get", return_value=mock_response) as mock_get:
            result = image_task_processor._fetch_image_content(mock_task_data)
            
            mock_get.assert_called_once_with(
                mock_task_data["url"],
                headers={
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
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                },
                timeout=30
            )
            assert result["type"] == "image/jpeg"
            assert result["content"] == b"fake_image_content"

    def test_fetch_image_content_invalid_type(self, image_task_processor, mock_task_data):
        """测试获取图片内容时遇到无效的内容类型"""
        mock_response = Mock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html>Not an image</html>"

        with patch("requests.get", return_value=mock_response) as mock_get:
            with pytest.raises(ImageDownloadError) as exc_info:
                image_task_processor._fetch_image_content(mock_task_data)
            assert "Unexpected content type" in str(exc_info.value)

    def test_fetch_image_content_network_error(self, image_task_processor, mock_task_data):
        """测试获取图片内容时遇到网络错误"""
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            with pytest.raises(ImageDownloadError) as exc_info:
                image_task_processor._fetch_image_content(mock_task_data)
            assert "Failed to download image" in str(exc_info.value)

    def test_save_image_metadata_success(self, image_task_processor, mock_image_data):
        """测试成功保存图片元数据"""
        with patch("weibo_favorites.crawler.tasks.save_image_metadata", return_value=None) as mock_save:
            image_task_processor._save_image_metadata(mock_image_data)
            mock_save.assert_called_once_with(mock_image_data)

    def test_save_image_metadata_failure(self, image_task_processor, mock_image_data):
        """测试保存图片元数据失败"""
        with patch("weibo_favorites.crawler.tasks.save_image_metadata") as mock_save:
            mock_save.side_effect = Exception("Database error")
            with pytest.raises(ImageMetadataSaveError) as exc_info:
                image_task_processor._save_image_metadata(mock_image_data)
            assert mock_image_data["weibo_id"] == exc_info.value.weibo_id
            assert mock_image_data["pic_id"] == exc_info.value.pic_id

    def test_process_and_save_image_success(self, image_task_processor, mock_image_data):
        """测试成功处理和保存图片"""
        mock_processed_images = {"thumbnail": b"fake_thumbnail"}
        
        with patch("weibo_favorites.crawler.tasks.process_image", return_value=mock_processed_images) as mock_process, \
             patch("weibo_favorites.crawler.tasks.update_image_process_result", return_value=None) as mock_update:
            
            result = image_task_processor._process_and_save_image(mock_image_data)
            
            # 直接使用 content 字段的内容
            mock_process.assert_called_once_with(mock_image_data["content"])
            mock_update.assert_called_once_with(
                mock_image_data["weibo_id"],
                mock_image_data["pic_id"],
                mock_processed_images
            )
            
            assert result["success"] is True
            assert result["weibo_id"] == mock_image_data["weibo_id"]
            assert result["pic_id"] == mock_image_data["pic_id"]

    def test_process_and_save_image_processing_error(self, image_task_processor, mock_image_data):
        """测试处理和保存图片时遇到处理错误"""
        error_message = "Processing error"
        with patch("weibo_favorites.crawler.tasks.process_image", side_effect=Exception(error_message)) as mock_process, \
             patch("weibo_favorites.crawler.tasks.update_image_process_status", return_value=None) as mock_update_status:
            
            with pytest.raises(ImageProcessingError) as exc_info:
                image_task_processor._process_and_save_image(mock_image_data)
            
            mock_update_status.assert_called_once_with(
                mock_image_data["weibo_id"],
                mock_image_data["pic_id"],
                error_message
            )
            assert "处理图片失败" in str(exc_info.value)

    def test_process_success(self, image_task_processor, mock_task_data):
        """测试成功处理完整的图片任务流程"""
        mock_image_content = {"type": "image/jpeg", "content": b"fake_image_content"}
        mock_process_result = {
            "success": True,
            "weibo_id": mock_task_data["weibo_id"],
            "pic_id": mock_task_data["pic_id"]
        }
        
        with patch.object(image_task_processor, "_fetch_image_content", return_value=mock_image_content) as mock_fetch, \
             patch.object(image_task_processor, "_save_image_metadata") as mock_save, \
             patch.object(image_task_processor, "_process_and_save_image", return_value=mock_process_result) as mock_process:
            
            result = image_task_processor.process(mock_task_data)
            
            mock_fetch.assert_called_once_with(mock_task_data)
            mock_save.assert_called_once()
            mock_process.assert_called_once()
            
            assert result == mock_process_result

    def test_process_download_error(self, image_task_processor, mock_task_data):
        """测试处理图片任务时遇到下载错误"""
        with patch.object(
            image_task_processor, 
            "_fetch_image_content", 
            side_effect=ImageDownloadError("Download failed", mock_task_data["weibo_id"], mock_task_data["pic_id"])
        ):
            result = image_task_processor.process(mock_task_data)
            assert result["success"] is False
            assert "Download failed" in result["error"]

    def test_process_metadata_error(self, image_task_processor, mock_task_data):
        """测试处理图片任务时遇到元数据保存错误"""
        mock_image_content = {"type": "image/jpeg", "content": b"fake_image_content"}
        
        with patch.object(image_task_processor, "_fetch_image_content", return_value=mock_image_content), \
             patch.object(
                 image_task_processor,
                 "_save_image_metadata",
                 side_effect=ImageMetadataSaveError("Save failed", mock_task_data["weibo_id"], mock_task_data["pic_id"])
             ):
            result = image_task_processor.process(mock_task_data)
            assert result["success"] is False
            assert "Save failed" in result["error"]


class TestLongTextTaskProcessor:
    """长文本任务处理器测试类"""

    def test_validate_cookie_success(self, long_text_processor, mock_long_text_data):
        """测试成功验证Cookie"""
        with patch.object(long_text_processor.cookie_manager, "check_validity", return_value=(True, "")) as mock_check:
            long_text_processor._validate_cookie(mock_long_text_data["weibo_id"])
            mock_check.assert_called_once()

    def test_validate_cookie_failure(self, long_text_processor, mock_long_text_data):
        """测试Cookie验证失败"""
        error_message = "Cookie已过期"
        with patch.object(long_text_processor.cookie_manager, "check_validity", return_value=(False, error_message)):
            with pytest.raises(CookieValidationError) as exc_info:
                long_text_processor._validate_cookie(mock_long_text_data["weibo_id"])
            assert error_message in str(exc_info.value)
            assert exc_info.value.weibo_id == mock_long_text_data["weibo_id"]

    def test_validate_parameters_success(self, long_text_processor, mock_long_text_data):
        """测试成功验证参数"""
        weibo_id, url = long_text_processor._validate_parameters(mock_long_text_data)
        assert weibo_id == mock_long_text_data["weibo_id"]
        assert url == mock_long_text_data["url"]

    def test_validate_parameters_missing_url(self, long_text_processor):
        """测试缺少URL参数"""
        task_data = {"weibo_id": "test_weibo_123"}
        with pytest.raises(ParameterError) as exc_info:
            long_text_processor._validate_parameters(task_data)
        assert "缺少URL" in str(exc_info.value)
        assert exc_info.value.weibo_id == task_data["weibo_id"]

    def test_fetch_long_text_success(self, long_text_processor, mock_long_text_data):
        """测试成功获取长文本"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"longTextContent": "这是一段长文本"}}
        
        with patch("requests.get", return_value=mock_response) as mock_get:
            result = long_text_processor._fetch_long_text(
                mock_long_text_data["weibo_id"],
                mock_long_text_data["url"]
            )
            
            mock_get.assert_called_once()
            assert result == mock_response.json()

    def test_fetch_long_text_network_error(self, long_text_processor, mock_long_text_data):
        """测试获取长文本时遇到网络错误"""
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            with pytest.raises(TextFetchError) as exc_info:
                long_text_processor._fetch_long_text(
                    mock_long_text_data["weibo_id"],
                    mock_long_text_data["url"]
                )
            assert "请求失败" in str(exc_info.value)
            assert exc_info.value.weibo_id == mock_long_text_data["weibo_id"]

    def test_extract_long_text_success(self, long_text_processor, mock_long_text_data):
        """测试成功提取长文本"""
        mock_data = {"data": {"longTextContent": "这是一段长文本"}}
        result = long_text_processor._extract_long_text(mock_data, mock_long_text_data["weibo_id"])
        assert result == "这是一段长文本"

    def test_extract_long_text_missing_content(self, long_text_processor, mock_long_text_data):
        """测试提取长文本时内容缺失"""
        mock_data = {"data": {}}
        with pytest.raises(TextExtractError) as exc_info:
            long_text_processor._extract_long_text(mock_data, mock_long_text_data["weibo_id"])
        assert "未能从响应中提取到完整内容" in str(exc_info.value)
        assert exc_info.value.weibo_id == mock_long_text_data["weibo_id"]

    def test_save_long_text_success(self, long_text_processor, mock_long_text_data):
        """测试成功保存长文本"""
        long_text = "这是一段长文本"
        mock_time = "2025-01-03 23:14:20"
    
        with patch("weibo_favorites.crawler.tasks.update_weibo_content", return_value=None) as mock_update, \
             patch("weibo_favorites.crawler.tasks.datetime") as mock_datetime:
    
            mock_datetime.now.return_value.strftime.return_value = mock_time
            result = long_text_processor._save_long_text(mock_long_text_data["weibo_id"], long_text)
    
            mock_update.assert_called_once()
            assert result == mock_time

    def test_save_long_text_database_error(self, long_text_processor, mock_long_text_data):
        """测试保存长文本时数据库错误"""
        with patch("weibo_favorites.crawler.tasks.update_weibo_content", side_effect=Exception("Database error")):
            with pytest.raises(TextSaveError) as exc_info:
                long_text_processor._save_long_text(mock_long_text_data["weibo_id"], "测试文本")
            assert "保存长文本失败" in str(exc_info.value)
            assert exc_info.value.weibo_id == mock_long_text_data["weibo_id"]

    def test_process_success(self, long_text_processor, mock_long_text_data):
        """测试成功处理完整的长文本任务流程"""
        mock_time = "2025-01-03 23:14:20"
        long_text = "这是一段长文本"
        
        with patch.object(long_text_processor.cookie_manager, "check_validity", return_value=(True, "")), \
             patch.object(long_text_processor, "_fetch_long_text", return_value={"data": {"longTextContent": long_text}}), \
             patch.object(long_text_processor, "_save_long_text", return_value=mock_time):
            
            result = long_text_processor.process(mock_long_text_data)
            
            assert result["success"] is True
            assert result["weibo_id"] == mock_long_text_data["weibo_id"]
            assert result["content"] == long_text
            assert result["processed_at"] == mock_time

    def test_process_cookie_error(self, long_text_processor, mock_long_text_data):
        """测试处理长文本任务时Cookie验证失败"""
        error_message = "Cookie已过期"
        with patch.object(long_text_processor.cookie_manager, "check_validity", return_value=(False, error_message)):
            result = long_text_processor.process(mock_long_text_data)
            assert result["success"] is False
            assert result["weibo_id"] == mock_long_text_data["weibo_id"]
            assert error_message in result["error"]

    def test_process_unknown_error(self, long_text_processor, mock_long_text_data):
        """测试处理长文本任务时发生未知错误"""
        with patch.object(long_text_processor.cookie_manager, "check_validity", side_effect=Exception("Unknown error")):
            result = long_text_processor.process(mock_long_text_data)
            assert result["success"] is False
            assert result["weibo_id"] == mock_long_text_data["weibo_id"]
            assert "未知错误" in result["error"]
