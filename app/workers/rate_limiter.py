import time
import uuid
import math
import redis
from app.core.config import settings
from app.core.logging import logger

class RedisRateLimiter:
    def __init__(self, redis_url: str | None = None, key: str = "rate_limit:dm_send", max_requests: int = 10, window_seconds: int = 60):
        self.redis_url = redis_url or settings.REDIS_URL
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def acquire_slot(self) -> tuple[bool, float]:
        """
        Attempts to acquire a slot in the rolling window rate limiter.
        Returns (allowed: bool, wait_time_seconds: float)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        try:
            r = self.client
            pipeline = r.pipeline()
            # Clean up old timestamps outside window
            pipeline.zremrangebyscore(self.key, "-inf", window_start)
            # Get current count
            pipeline.zcard(self.key)
            # Get oldest timestamp in window
            pipeline.zrange(self.key, 0, 0, withscores=True)
            results = pipeline.execute()

            current_count = results[1]
            oldest_items = results[2]

            if current_count >= self.max_requests:
                if oldest_items:
                    oldest_ts = oldest_items[0][1]
                    wait_time = (oldest_ts + self.window_seconds) - now + 0.5
                else:
                    wait_time = float(self.window_seconds)
                wait_time = max(1.0, math.ceil(wait_time))
                logger.info("Rate limit reached (%d/%d). Must wait %f seconds.", current_count, self.max_requests, wait_time)
                return False, wait_time

            # Acquire slot
            member = f"{now}-{uuid.uuid4().hex[:8]}"
            pipeline = r.pipeline()
            pipeline.zadd(self.key, {member: now})
            pipeline.expire(self.key, self.window_seconds + 10)
            pipeline.execute()
            return True, 0.0
        except Exception as e:
            logger.error("Redis rate limiter error: %s. Defaulting to allowing call.", e)
            return True, 0.0
