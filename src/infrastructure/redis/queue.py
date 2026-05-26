import os
import redis
import logging
from typing import Optional
from src.use_cases.create_notification import NotificationScheduler


logger = logging.getLogger(__name__)


class RedisSchedulerQueue(NotificationScheduler):
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.queue_key = "delayed_notifications"
        self.client: Optional[redis.Redis] = None
        self._pop_due_item_script = None
        
        script_path = os.path.join(os.path.dirname(__file__), "scripts", "pop_due_item.lua")
        with open(script_path, "r") as f:
            self.lua_script = f.read()

    def _ensure_connected(self):
        """Ensures that the Redis client is connected. If not, it attempts to reconnect."""
        if self.client is None:
            try:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                self.client.ping()
                self._pop_due_item_script = self.client.register_script(self.lua_script)
                logger.info("Successfully connected to Redis.")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self.client = None

    def schedule(self, notification_id: str, timestamp: float) -> None:
        self._ensure_connected()
        if self.client:
            try:
                self.client.zadd(self.queue_key, {notification_id: timestamp})
            except redis.ConnectionError:
                self.client = None

    def pop_due_item(self, current_time: float) -> Optional[str]:
        self._ensure_connected()
        if not self.client or not self._pop_due_item_script:
            return None
        
        try:
            return self._pop_due_item_script(keys=[self.queue_key], args=[current_time])
        except redis.ConnectionError:
            logger.warning("Redis connection lost during pop. Resetting client...")
            self.client = None
            return None
    