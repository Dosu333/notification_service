import uuid
import copy
import logging
from croniter import croniter
from datetime import datetime, timezone
from src.domain.entities import OutboxEvent
from src.interfaces.repositories import NotificationRepository, UnitOfWork
from src.use_cases.create_notification import NotificationScheduler
from src.interfaces.providers import UserPreferenceProvider
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


logger = logging.getLogger(__name__)


class ProcessScheduledNotificationUseCase:
    def __init__(
        self, 
        repo: NotificationRepository, 
        unit_of_work: UnitOfWork,
        scheduler: NotificationScheduler,
        preference_provider: UserPreferenceProvider,
        metrics: PrometheusMetricsService
    ):
        self.repo = repo
        self.unit_of_work = unit_of_work
        self.scheduler = scheduler
        self.preference_provider = preference_provider
        self.metrics = metrics

    def execute(self, notification_id_str: str, correlation_id: str) -> bool:
        notification_id = uuid.UUID(notification_id_str)
        notification = self.repo.get_by_id(notification_id)
        
        if not notification or notification.status != "SCHEDULED":
            return False
        
        # Preference Check
        can_send = self.preference_provider.can_receive(
            user_id=notification.user_id,
            channel=notification.channel,
            template=notification.template
        )

        if not can_send:
            logger.info(f"[{correlation_id}] Late-bound preference check failed. Suppressing notification {notification_id_str}.")
            notification.status = "SUPPRESSED"
            self.unit_of_work.commit_notification(notification)
            return True

        # Recurrence Handling: If the notification has a recurrence rule, 
        # calculate the next occurrence and prepare it for scheduling
        next_notification = None
        if getattr(notification, "recurrence_rule", None):
            now = datetime.now(timezone.utc)
            try:
                # Calculate the next occurrence based on the cron rule
                cron = croniter(notification.recurrence_rule, now)
                next_date = cron.get_next(datetime)
                
                # Clone the notification for the future
                next_notification = copy.deepcopy(notification)
                next_notification.id = uuid.uuid4()
                next_notification.status = "SCHEDULED"
                next_notification.scheduled_at = next_date
                next_notification.created_at = now
                next_notification.updated_at = now
                
                # Generate a new idempotency key for the next occurrence
                base_key = notification.idempotency_key.split('_')[0] 
                next_notification.idempotency_key = f"{base_key}_{int(next_date.timestamp())}"
                
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to parse recurrence rule for {notification_id_str}: {e}")

        # Process current notification
        notification.status = "QUEUED"
        
        # Ensure the outbox key is unique for this execution
        outbox_idempotency_key = f"{notification.idempotency_key}_outbox_{int(notification.scheduled_at.timestamp())}"
        
        outbox_payload = {
            "notification_id": str(notification.id),
            "user_id": notification.user_id,
            "channel": notification.channel,
            "template": notification.template,
            "payload": notification.payload,
            "idempotency_key": outbox_idempotency_key,
            "correlation_id": correlation_id
        }
        outbox_event = OutboxEvent(topic="notification.events", payload=outbox_payload)

        # Atomic Database Commit
        if next_notification:
            self.unit_of_work.commit_recurring_dispatch(
                current_notification=notification, 
                outbox_event=outbox_event,
                next_notification=next_notification
            )
        else:
            # One-off notification commit
            self.unit_of_work.commit_notification_and_outbox(
                notification=notification, 
                outbox_event=outbox_event
            )

        # Schedule the next occurrence if it exists
        if next_notification:
            self.scheduler.schedule(str(next_notification.id), next_notification.scheduled_at.timestamp())
            
        self.metrics.inc_scheduled_fired()
        return True
