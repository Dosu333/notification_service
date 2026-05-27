import os
import time
import redis
import logging
from typing import Tuple, Optional


logger = logging.getLogger(__name__)


class RedisRateLimiter:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self._script_sha = None
        
        script_path = os.path.join(os.path.dirname(__file__), "scripts", "sliding_window_rate_limit.lua")
        with open(script_path, "r") as f:
            try:
                self.lua_script = f.read()
            except Exception as e:
                logger.error(f"Error reading Lua script: {e}")
                self.lua_script = ""

    def _ensure_connected(self):
        """Lazy-init the Redis connection and load the Lua script into Redis RAM."""
        if self.client is None and self.lua_script:
            try:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                # register_script caches the Lua script in Redis and returns a callable SHA
                self._script_sha = self.client.register_script(self.lua_script)
            except redis.ConnectionError:
                logger.warning("Redis offline. Rate limiter will fail open.")
                self.client = None

    def is_allowed(self, identifier: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        self._ensure_connected()
        
        # FAIL OPEN: If Redis crashes or script is missing, allow traffic.
        if not self.client or not self._script_sha:
            return True, limit 
            
        redis_key = f"rate_limit:{identifier}"
        now = time.time()
        random_val = str(now) 
        
        try:
            result = self._script_sha(
                keys=[redis_key], 
                args=[now, window_seconds, limit, random_val]
            )
            return bool(result[0]), int(result[1])
        except redis.ConnectionError:
            self.client = None
            return True, limit