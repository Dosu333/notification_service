from abc import ABC, abstractmethod
from typing import Optional
from src.domain.entities import Notification, OutboxEvent


class NotificationRepository(ABC):
    @abstractmethod
    def save(self, notification: Notification) -> None:
        pass

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Optional[Notification]:
        pass

    @abstractmethod
    def update(self, notification: Notification) -> None:
        pass


class UnitOfWork(ABC):
    """
    Ensures that saving a Notification and an OutboxEvent 
    happens in the same database transaction.
    """
    @abstractmethod
    def commit_notification_and_outbox(
        self, notification: Notification, outbox_event: OutboxEvent
    ) -> None:
        pass
