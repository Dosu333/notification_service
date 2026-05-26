import uuid
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from src.domain.entities import Notification, OutboxEvent
from src.interfaces.repositories import NotificationRepository, UnitOfWork
from src.interfaces.scheduling import NotificationScheduler
from src.interfaces.providers import IdempotencyProvider
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


class NotificationStatus(str, Enum):
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    SUPPRESSED = "SUPPRESSED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"


@dataclass
class CreateNotificationRequest:
    user_id: str
    channel: str
    payload: Dict[str, Any]
    idempotency_key: str
    template: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    recurrence_rule: Optional[str] = None
    timezone: str = "UTC"


@dataclass
class CreateNotificationResponse:
    success: bool
    message: str
    status: NotificationStatus
    notification_id: Optional[uuid.UUID] = None


class IdempotencyConflictException(Exception):
    pass


class CreateNotificationUseCase:
    def __init__(
        self, 
        notification_repo: NotificationRepository, 
        unit_of_work: UnitOfWork,
        scheduler: NotificationScheduler,
        metrics: PrometheusMetricsService,
        idempotency_provider: IdempotencyProvider 
    ):
        self.notification_repo = notification_repo
        self.unit_of_work = unit_of_work
        self.scheduler = scheduler 
        self.metrics = metrics
        self.idempotency_provider = idempotency_provider

    def execute(self, request: CreateNotificationRequest) -> CreateNotificationResponse:
        
        # Redis Distributed Lock (Short-Term Protection)
        if request.idempotency_key:
            lock_acquired = self.idempotency_provider.acquire_lock(request.idempotency_key)
            if not lock_acquired:
                raise IdempotencyConflictException(
                    f"Request {request.idempotency_key} is currently processing."
                )

        # Idempotency Check: Database Layer (Long-Term Protection)
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
            template=request.template,
            scheduled_at=request.scheduled_at,
            recurrence_rule=request.recurrence_rule,
            timezone=request.timezone
        )

        if notification.scheduled_at:
            notification.mark_as_scheduled()

            # Save only the notification to the database
            self.unit_of_work.commit_notification(notification)

            # Push to scheduler (e.g., Redis Sorted Set) with the scheduled timestamp as score
            unix_timestamp = notification.scheduled_at.timestamp()
            self.scheduler.schedule(str(notification.id), unix_timestamp)
            self.metrics.inc_scheduled_registered()

            return CreateNotificationResponse(
                success=True,
                message="Notification successfully scheduled.",
                notification_id=notification.id
            )

        else:
            topic = "notification.events"
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

            # Atomic save of both notification and outbox event
            self.unit_of_work.commit_notification_and_outbox(
                notification=notification, 
                outbox_event=outbox_event
            )

            return CreateNotificationResponse(
                success=True,
                message="Notification successfully queued.",
                notification_id=notification.id
            )
