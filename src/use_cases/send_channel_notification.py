import logging
import uuid
from typing import Optional
from src.interfaces.repositories import NotificationRepository
from src.interfaces.providers import EmailProvider, SMSProvider, ProviderError


logger = logging.getLogger(__name__)


class SendChannelNotificationUseCase:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        email_provider: Optional[EmailProvider] = None,
        sms_provider: Optional[SMSProvider] = None
    ):
        self.notification_repo = notification_repo
        self.email_provider = email_provider
        self.sms_provider = sms_provider

    def execute(self, notification_id: uuid.UUID) -> None:
        """
        Executes the safe dispatch of a notification to an external provider.
        """
        notification = self.notification_repo.get_by_id(notification_id)
        
        if not notification:
            logger.error(f"Critical: Notification {notification_id} not found in database.")
            return

        if notification.status in ["SENT", "DELIVERED"]:
            logger.info(
                f"Idempotency hit: Notification {notification_id} is already {notification.status}. "
                "Dropping duplicate message."
            )
            return

        try:
            provider_message_id = None
            provider_name = "UNKNOWN"

            if notification.channel == "email" and self.email_provider:
                provider_name = "EMAIL_PROVIDER" 
                provider_message_id = self.email_provider.send(
                    recipient_email=notification.payload.get("recipient_email"),
                    subject=notification.payload.get("subject"),
                    body_text=notification.payload.get("body_text"),
                    template_id=notification.template,
                    template_data=notification.payload.get("template_data")
                )
                
            elif notification.channel == "sms" and self.sms_provider:
                provider_name = "SMS_PROVIDER"
                provider_message_id = self.sms_provider.send(
                    phone_number=notification.payload.get("phone_number"),
                    message=notification.payload.get("message")
                )
                
            else:
                raise ValueError(f"Unsupported channel or missing provider setup for: {notification.channel}")

            notification.mark_as_sent(provider_name=provider_name)
            
            # TODO: Add a `provider_message_id` column 
            # to DB and pure entity to store this ID for webhook reconciliation.
            # notification.provider_message_id = provider_message_id 
            
            self.notification_repo.update(notification)
            logger.info(f"Successfully dispatched notification {notification_id} via {provider_name}.")

        except ProviderError as e:
            notification.mark_as_failed()
            self.notification_repo.update(notification)
            logger.error(f"Provider failed to send {notification_id}. Retry count is now {notification.retry_count}.")
            raise e