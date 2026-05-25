import uuid
from src.domain.entities import OutboxEvent
from src.interfaces.repositories import NotificationRepository, UnitOfWork
from src.use_cases.create_notification import NotificationScheduler


class ProcessScheduledNotificationUseCase:
    def __init__(
        self, 
        repo: NotificationRepository, 
        unit_of_work: UnitOfWork,
        scheduler: NotificationScheduler
    ):
        self.repo = repo
        self.unit_of_work = unit_of_work
        self.scheduler = scheduler

    def execute(self, notification_id_str: str, correlation_id: str) -> bool:
        notification_id = uuid.UUID(notification_id_str)
        notification = self.repo.get_by_id(notification_id)
        
        if not notification or notification.status != "SCHEDULED":
            return False

        # Generate a unique idempotency key for this scheduled event to prevent duplicates in the Outbox
        unique_idempotency_key = f"{notification.idempotency_key}_{int(notification.scheduled_at.timestamp())}"
        
        outbox_payload = {
            "notification_id": str(notification.id),
            "user_id": notification.user_id,
            "channel": notification.channel,
            "template": notification.template,
            "payload": notification.payload,
            "idempotency_key": unique_idempotency_key,
            "correlation_id": correlation_id
        }
        outbox_event = OutboxEvent(topic="notification.events", payload=outbox_payload)
        is_recurring = notification.process_scheduling()

        # Atomic Database Commit
        self.unit_of_work.commit_notification_and_outbox(
            notification=notification, 
            outbox_event=outbox_event
        )

        # Reschedule if it's a recurring notification
        if is_recurring:
            next_timestamp = notification.scheduled_at.timestamp()
            self.scheduler.schedule(str(notification.id), next_timestamp)

        return True
