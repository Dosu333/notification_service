from src.interfaces.repositories import NotificationRepository
from src.use_cases.create_notification import NotificationScheduler
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


class BootstrapSchedulerUseCase:
    def __init__(
        self,
        repo: NotificationRepository,
        scheduler: NotificationScheduler,
        metrics: PrometheusMetricsService
    ):
        self.repo = repo
        self.scheduler = scheduler
        self.metrics = metrics

    def execute(self) -> int:
        """
        Reads all SCHEDULED notifications from the source of truth (Postgres)
        and blindly pushes them to the in-memory cache (Redis).
        Because Redis ZADD is idempotent, this is 100% safe to run repeatedly.
        """
        scheduled_notifications = self.repo.get_all_scheduled()
        count = 0
        
        for notification in scheduled_notifications:
            if notification.scheduled_at:
                unix_timestamp = notification.scheduled_at.timestamp()
                self.scheduler.schedule(str(notification.id), unix_timestamp)
                count += 1
        
        if count > 0:
            self.metrics.inc_redis_sync(count)
                
        return count