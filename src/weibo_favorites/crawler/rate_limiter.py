"""
速率限制器模块
"""

import random
import time
from datetime import datetime, timedelta
from typing import Optional

import redis

from ..utils import LogManager

logger = LogManager.setup_logger("rate_limiter")


class RateLimiter:
    """漏桶速率限制器"""

    def __init__(self, redis_conn: redis.Redis, key: str, rate: int, window: int = 60):
        """初始化速率限制器

        Args:
            redis_conn: Redis连接
            key: 速率限制器的键名
            rate: 单位时间内允许的最大请求数
            window: 时间窗口大小（秒）
        """
        self.redis = redis_conn
        self.key = f"rate_limit:{key}"
        self.rate = rate
        self.window = window
        # 计算请求之间的基础间隔时间
        self.base_interval = window / rate

    def _get_random_interval(self) -> float:
        """生成带随机性的间隔时间

        Returns:
            实际等待时间（秒）
        """
        # 在基础间隔时间的基础上增加 ±20% 的随机波动
        variation = self.base_interval * 0.2
        return self.base_interval + random.uniform(-variation, variation)

    def get_next_execution_time(self) -> Optional[datetime]:
        """获取下一个可执行时间

        Returns:
            下一个可执行时间，如果无法获取则返回 None
        """
        now = datetime.now()
        last_request_key = f"{self.key}:last"
        
        # 获取上一次请求的时间
        last_request = self.redis.get(last_request_key)
        if last_request:
            last_request_time = datetime.fromtimestamp(float(last_request.decode('utf-8')))
            # 计算下一个执行时间
            interval = self._get_random_interval()
            next_time = last_request_time + timedelta(seconds=interval)
            
            # 如果下一个执行时间已经过去，就返回当前时间
            if next_time < now:
                next_time = now
                
            # 更新下一次执行时间
            self.redis.set(
                last_request_key,
                str(next_time.timestamp()),
                ex=self.window * 2
            )
            return next_time
            
        # 如果没有上一次请求记录，可以立即执行
        self.redis.set(
            last_request_key,
            str(now.timestamp()),
            ex=self.window * 2
        )
        return now

    def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """等待直到获取到令牌或超时

        Args:
            timeout: 超时时间（秒），None表示一直等待

        Returns:
            是否成功获取令牌
        """
        now = time.time()
        last_request_key = f"{self.key}:last"
        
        # 获取上一次请求的时间
        last_request = self.redis.get(last_request_key)
        if last_request:
            last_request = float(last_request.decode('utf-8'))
            # 计算实际需要等待的时间
            interval = self._get_random_interval()
            wait_time = max(0, last_request + interval - now)
            
            if timeout is not None and wait_time > timeout:
                logger.warning(f"等待令牌超时，需要等待 {wait_time:.2f} 秒，但超时限制为 {timeout} 秒")
                return False
                
            if wait_time > 0:
                logger.debug(f"等待 {wait_time:.2f} 秒后发起请求")
                time.sleep(wait_time)
        
        # 更新上一次请求时间并设置过期时间
        self.redis.set(last_request_key, str(time.time()), ex=self.window * 2)
        return True
