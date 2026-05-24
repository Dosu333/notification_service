import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional
from src.domain.entities import Notification, OutboxEvent
from src.interfaces.repositories import NotificationRepository, UnitOfWork


@dataclass
class CreateNotificationRequest:
    user_id: str
    channel: str
    payload: Dict[str, Any]
    idempotency_key: str
    template: Optional[str] = None


@dataclass
class CreateNotificationResponse:
    success: bool
    message: str
    notification_id: Optional[uuid.UUID] = None


class CreateNotificationUseCase:
    def __init__(
        self, 
        notification_repo: NotificationRepository, 
        unit_of_work: UnitOfWork
    ):
        self.notification_repo = notification_repo
        self.unit_of_work = unit_of_work

    def execute(self, request: CreateNotificationRequest) -> CreateNotificationResponse:
        # Idempotency Check
        existing_notification = self.notification_repo.get_by_idempotency_key(
            request.idempotency_key
        )
        
        if existing_notification:
            return CreateNotificationResponse(
                success=True,
                message="Notification already processed.",
                notification_id=existing_notification.id
            )

        notification = Notification(
            user_id=request.user_id,
            channel=request.channel,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
            template=request.template
        )
        
        # Route message to the correct queue topic based on the channel
        topic = f"{request.channel}.queue"
        outbox_payload = {
            "notification_id": str(notification.id),
            "user_id": notification.user_id,
            "channel": notification.channel,
            "template": notification.template,
            "payload": notification.payload
        }
        
        outbox_event = OutboxEvent(
            topic=topic,
            payload=outbox_payload
        )

        self.unit_of_work.commit_notification_and_outbox(
            notification=notification, 
            outbox_event=outbox_event
        )

        return CreateNotificationResponse(
            success=True,
            message="Notification successfully queued.",
            notification_id=notification.id
        )
