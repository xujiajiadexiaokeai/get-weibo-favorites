"""媒体处理模块"""

import io
from PIL import Image
from typing import Dict

"""图片处理子模块"""
def process_image(image_data: bytes, max_width: int = 1024) -> Dict[str, bytes]:
    """处理图片，生成缩略图和压缩后的图片

    Args:
        image_data: 原始图片数据
        max_width: 最大宽度，默认1024px

    Returns:
        包含处理后图片的字典:
        {
            'thumbnail': 缩略图数据(WebP格式),
            'compressed': 压缩后的图片数据(WebP格式)
        }
    """
    # 从字节数据创建图片对象
    img = Image.open(io.BytesIO(image_data))

    # 生成缩略图
    thumb_size = (200, 200)  # 缩略图尺寸
    thumb = img.copy()
    thumb.thumbnail(thumb_size, Image.Resampling.LANCZOS)

    # 压缩原图
    if img.size[0] > max_width:
        ratio = max_width / img.size[0]
        new_size = (max_width, int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # 转换为字节数据
    thumb_buffer = io.BytesIO()
    thumb.save(thumb_buffer, format='webp', quality=85, optimize=True)
    thumb_data = thumb_buffer.getvalue()

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='webp', quality=85, optimize=True)
    img_data = img_buffer.getvalue()

    return {
        'thumbnail': thumb_data,
        'compressed': img_data
    }
