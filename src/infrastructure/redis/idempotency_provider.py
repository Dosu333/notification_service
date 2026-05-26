import redis
import logging
from typing import Optional
from src.interfaces.providers import IdempotencyProvider


logger = logging.getLogger(__name__)


class RedisIdempotencyProvider(IdempotencyProvider):
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None

    def _ensure_connected(self):
        if self.client is None:
            try:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                self.client.ping()
            except Exception as e:
                logger.error(f"Redis Idempotency connection failed: {e}")
                self.client = None

    def acquire_lock(self, idempotency_key: str, ttl_seconds: int = 86400) -> bool:
        self._ensure_connected()

        if self.client is None:
            logger.warning("Redis is down. Failing open and allowing request to proceed.")
            return True 
            
        redis_key = f"idempotency:lock:{idempotency_key}"
        
        try:
            # SETNX (Set if Not eXists). Returns True if set, False if already exists.
            acquired = self.client.set(redis_key, "LOCKED", nx=True, ex=ttl_seconds)
            return bool(acquired)
            
        except redis.ConnectionError:
            logger.warning("Lost Redis connection during lock attempt. Failing open.")
            self.client = None
            return True
