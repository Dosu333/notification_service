import json
import redis
import logging
from typing import Optional
from src.interfaces.providers import UserPreferenceProvider
from src.interfaces.repositories import UserPreferenceRepository


logger = logging.getLogger(__name__)


class RedisUserPreferenceProvider(UserPreferenceProvider):
    def __init__(self, redis_url: str, db_repo: UserPreferenceRepository):
        self.redis_url = redis_url
        self.db_repo = db_repo
        self.client: Optional[redis.Redis] = None
        self.ttl_seconds = 300

    def _ensure_connected(self):
        """Lazy-init the Redis connection with self-healing."""
        if self.client is None:
            try:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                self.client.ping()
            except Exception as e:
                logger.error(f"Redis Preference connection failed: {e}")
                self.client = None

    def can_receive(self, user_id: str, channel: str, template: Optional[str] = None) -> bool:
        self._ensure_connected()
        
        redis_key = f"prefs:{user_id}"
        prefs_dict = None

        # Attempt to read from Redis cache first (Short-Term Protection)
        if self.client:
            try:
                cached_data = self.client.get(redis_key)
                if cached_data:
                    prefs_dict = json.loads(cached_data)
            except redis.ConnectionError:
                logger.warning("Redis connection lost during read. Falling back to Postgres.")
                self.client = None

        # If cache miss or Redis down, read from DB and update cache (Long-Term Protection)
        if prefs_dict is None:
            prefs_dict = self.db_repo.get_by_user_id(user_id)
            
            # If user has no record in DB, assume default permissive settings
            if not prefs_dict:
                prefs_dict = {"dnd": False, "channels": {}, "templates": {}}
            
            # Update Redis cache 
            if self.client:
                try:
                    self.client.setex(
                        name=redis_key, 
                        time=self.ttl_seconds, 
                        value=json.dumps(prefs_dict)
                    )
                except redis.ConnectionError:
                    self.client = None

        return self._evaluate_preferences(prefs_dict, channel, template)

    def _evaluate_preferences(self, prefs: dict, channel: str, template: Optional[str]) -> bool:
        """Core logic to check DND, channel opt-outs, and template opt-outs."""
        if prefs.get("dnd") is True:
            return False

        channel_prefs = prefs.get("channels", {})
        if channel.upper() in channel_prefs and channel_prefs[channel.upper()] is False:
            return False

        if template:
            template_prefs = prefs.get("templates", {})
            if template.lower() in template_prefs and template_prefs[template.lower()] is False:
                return False
                
        return True