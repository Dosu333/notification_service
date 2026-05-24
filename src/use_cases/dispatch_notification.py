import logging
from typing import Dict, Any
from src.interfaces.messaging import MessageBroker


logger = logging.getLogger(__name__)


class DispatchNotificationUseCase:
    def __init__(
        self, 
        message_broker: MessageBroker
    ):
        self.message_broker = message_broker
        
        # In a real system, this would come from a config service or Redis cache
        self.GLOBAL_SMS_ENABLED = True 
        self.ALLOWED_CHANNELS = ["email", "sms", "push"]

    def execute(self, event_payload: Dict[str, Any]) -> None:
        """
        Processes a raw event from the 'notification.events' topic 
        and routes it to the specific channel queue.
        """
        try:
            # 1. Extract core data
            notification_id = event_payload.get("notification_id")
            user_id = event_payload.get("user_id")
            requested_channel = event_payload.get("channel")
            
            if not all([notification_id, user_id, requested_channel]):
                raise ValueError(f"Malformed event payload missing critical fields: {event_payload}")

            # Evaluate Global Rules
            if requested_channel not in self.ALLOWED_CHANNELS:
                logger.warning(f"Unsupported channel '{requested_channel}' for notification {notification_id}. Dropping.")
                return

            if requested_channel == "sms" and not self.GLOBAL_SMS_ENABLED:
                logger.info(f"Global SMS disabled. Falling back to email for {notification_id}.")
                requested_channel = "email"

            # Route to the correct downstream topic
            target_topic = f"{requested_channel}.queue"
            
            # Publish to the specific channel worker
            self.message_broker.publish(
                topic=target_topic,
                payload=event_payload
            )
            
            logger.info(f"Successfully dispatched notification {notification_id} to {target_topic}")

        except Exception as e:
            logger.error(f"Failed to dispatch notification: {e}")
            raise e