import logging
from dataclasses import dataclass
from src.interfaces.repositories import NotificationRepository


logger = logging.getLogger(__name__)


@dataclass
class DeliveryReceiptDTO:
    provider_message_id: str
    status: str  # e.g., "DELIVERED", "FAILED"
    provider_name: str
    error_details: str = ""
    

class HandleDeliveryReceiptUseCase:
    def __init__(self, notification_repo: NotificationRepository):
        self.notification_repo = notification_repo

    def execute(self, receipt: DeliveryReceiptDTO) -> None:
        """
        Updates the final state of a notification based on provider callbacks.
        """
        notification = self.notification_repo.get_by_provider_message_id(
            receipt.provider_message_id
        )

        if not notification:
            logger.warning(
                f"Received webhook for unknown message ID: {receipt.provider_message_id}. "
                "This could be an old message or a dev environment crossover."
            )
            return

        if notification.status == "DELIVERED":
            return

        if receipt.status == "DELIVERED":
            notification.status = "DELIVERED"
            logger.info(f"Notification {notification.id} confirmed DELIVERED via {receipt.provider_name}.")
        
        elif receipt.status == "FAILED":
            notification.status = "FAILED"
            notification.error_message = receipt.error_details
            logger.error(f"Notification {notification.id} FAILED delivery. Reason: {receipt.error_details}")

        self.notification_repo.update(notification)
