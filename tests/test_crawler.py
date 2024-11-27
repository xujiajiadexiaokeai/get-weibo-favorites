import json

from weibo_favorites import config
from weibo_favorites.utils import setup_logger
from weibo_favorites.auth import load_cookies, create_session
from weibo_favorites.crawler import get_favorites

# 设置日志记录器
logger = setup_logger(__name__)

def test_get_first_page():
    """测试获取第一页收藏数据"""
    try:
        # 加载cookies
        cookies = load_cookies()
        if not cookies:
            logger.error("无法加载cookies，请先运行 auth.py 获取cookies")
            return
        
        # 创建会话
        session = create_session(cookies)
        
        # 获取第一页数据
        logger.info("开始获取第一页数据...")
        favorites = get_favorites(session, page=1)
        
        # 输出结果
        if favorites:
            logger.info(f"成功获取 {len(favorites)} 条收藏")
            # 保存结果到文件以便查看
            with open(config.DATA_DIR / "test_favorites.json", "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
            logger.info(f"成功获取并保存了 {len(favorites)} 条收藏")
        else:
            logger.warning("未获取到任何收藏数据")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise
    finally:
        if 'session' in locals() and session:
            session.close()

if __name__ == '__main__':
    test_get_first_page()
