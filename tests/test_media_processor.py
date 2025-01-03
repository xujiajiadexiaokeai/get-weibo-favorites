import unittest
import base64
from PIL import Image
import io
from src.weibo_favorites.crawler.media_processor import decode_data_url, process_image

class TestMediaProcessor(unittest.TestCase):
    def setUp(self):
        # 创建一个测试用的图片数据
        img = Image.new('RGB', (1500, 1000), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        self.test_image_bytes = img_buffer.getvalue()
        
        # 创建对应的Data URL
        self.test_data_url = f"data:image/jpeg;base64,{base64.b64encode(self.test_image_bytes).decode()}"

    def test_decode_data_url_valid(self):
        """测试解码有效的Data URL"""
        decoded = decode_data_url(self.test_data_url)
        self.assertEqual(decoded, self.test_image_bytes)

    def test_decode_data_url_invalid(self):
        """测试解码无效的Data URL"""
        invalid_data_url = "invalid_data_url"
        with self.assertRaises(ValueError):
            decode_data_url(invalid_data_url)

    def test_process_image_basic(self):
        """测试基本的图片处理功能"""
        result = process_image(self.test_image_bytes)
        
        # 验证返回的字典包含必要的键
        self.assertIn('thumbnail', result)
        self.assertIn('compressed', result)
        
        # 验证返回的是字节数据
        self.assertIsInstance(result['thumbnail'], bytes)
        self.assertIsInstance(result['compressed'], bytes)

    def test_process_image_thumbnail_size(self):
        """测试缩略图尺寸"""
        result = process_image(self.test_image_bytes)
        
        # 读取缩略图并验证尺寸
        thumb = Image.open(io.BytesIO(result['thumbnail']))
        self.assertLessEqual(thumb.size[0], 200)
        self.assertLessEqual(thumb.size[1], 200)

    def test_process_image_compression(self):
        """测试大图压缩"""
        result = process_image(self.test_image_bytes)
        
        # 读取压缩后的图片并验证尺寸
        compressed = Image.open(io.BytesIO(result['compressed']))
        self.assertLessEqual(compressed.size[0], 1024)

    def test_process_image_format(self):
        """测试输出格式为WebP"""
        result = process_image(self.test_image_bytes)
        
        # 验证缩略图格式
        thumb = Image.open(io.BytesIO(result['thumbnail']))
        self.assertEqual(thumb.format.lower(), 'webp')
        
        # 验证压缩图格式
        compressed = Image.open(io.BytesIO(result['compressed']))
        self.assertEqual(compressed.format.lower(), 'webp')

if __name__ == '__main__':
    unittest.main()
