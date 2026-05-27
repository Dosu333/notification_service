import redis
import logging
import datetime
from typing import Optional
from src.interfaces.providers import UserQuotaProvider


logger = logging.getLogger(__name__)


class RedisUserQuotaProvider(UserQuotaProvider):
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None

    def _ensure_connected(self):
        """Lazy-init the Redis connection with self-healing."""
        if self.client is None:
            try:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                self.client.ping()
            except redis.ConnectionError:
                logger.error("Redis connection failed for Quota Provider.")
                self.client = None

    def decrement(self, user_id: str, daily_limit: int) -> int:
        self._ensure_connected()
        
        if not self.client:
            logger.warning(f"Redis is down. Failing open for user {user_id} promotional quota.")
            return 1 

        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        redis_key = f"quota:promo:{user_id}:{today}"
        
        try:
            # INCR is atomic. If the key doesn't exist, it creates it and sets to 1.
            usage = self.client.incr(redis_key)

            if usage == 1:
                self.client.expire(redis_key, 86400) # 86400 seconds = 24 hours
                
            remaining = daily_limit - usage
            return remaining
            
        except redis.ConnectionError:
            self.client = None
            return 1