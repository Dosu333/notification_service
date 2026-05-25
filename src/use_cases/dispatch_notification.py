import logging
from typing import Dict, Any
from src.interfaces.messaging import MessageBroker
from src.interfaces.repositories import UserPreferenceRepository
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()

logger = logging.getLogger(__name__)


class DispatchNotificationUseCase:
    def __init__(
        self, 
        message_broker: MessageBroker,
        user_preference_repo: UserPreferenceRepository
    ):
        self.message_broker = message_broker
        self.user_preference_repo = user_preference_repo
        
        self.GLOBAL_SMS_ENABLED = True 
        self.ALLOWED_CHANNELS = ["email", "sms", "push"]

    def execute(self, event_payload: Dict[str, Any]) -> None:
        try:
            notification_id = event_payload.get("notification_id")
            user_id = event_payload.get("user_id")
            requested_channel = event_payload.get("channel")
            
            if not all([notification_id, user_id, requested_channel]):
                raise ValueError("Malformed event payload missing critical fields.")

            if requested_channel not in self.ALLOWED_CHANNELS:
                logger.warning(f"Unsupported channel '{requested_channel}'. Dropping.")
                return

            if requested_channel == "sms" and not self.GLOBAL_SMS_ENABLED:
                logger.info(f"Global SMS disabled. Falling back to email for {notification_id}.")
                requested_channel = "email"

            user_prefs = self.user_preference_repo.get_by_user_id(user_id)
            
            if user_prefs.is_unsubscribed(requested_channel):
                logger.info(
                    f"User {user_id} is unsubscribed from {requested_channel}. "
                    f"Silently dropping notification {notification_id}."
                )
                return

            target_topic = f"{requested_channel}.queue"
            
            self.message_broker.publish(
                topic=target_topic,
                payload=event_payload
            )
            
            logger.info(f"Successfully dispatched notification {notification_id} to {target_topic}")

        except Exception as e:
            logger.error(f"Failed to dispatch notification: {e}")
            raise e
