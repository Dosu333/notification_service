import os
import redis
from typing import Optional
from src.use_cases.create_notification import NotificationScheduler


class RedisSchedulerQueue(NotificationScheduler):
    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.queue_key = "delayed_notifications"
        
        # Load and register the Lua script from disk
        script_path = os.path.join(
            os.path.dirname(__file__), 
            "scripts", 
            "pop_due_item.lua"
        )
        with open(script_path, "r") as f:
            lua_script = f.read()
            
        self._pop_due_item_script = self.client.register_script(lua_script)

    def schedule(self, notification_id: str, timestamp: float) -> None:
        """Used by the API (CreateNotificationUseCase) to park an item."""
        self.client.zadd(self.queue_key, {notification_id: timestamp})

    def pop_due_item(self, current_time: float) -> Optional[str]:
        """Used by the Scheduler Worker to atomicially grab due items."""
        return self._pop_due_item_script(keys=[self.queue_key], args=[current_time])