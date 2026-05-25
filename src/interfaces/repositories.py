import uuid
from abc import ABC, abstractmethod
from typing import Optional
from src.domain.entities import UserPreference, Notification, OutboxEvent


class UserPreferenceRepository(ABC):
    @abstractmethod
    def get_by_user_id(self, user_id: str) -> UserPreference:
        """
        Fetches preferences. If no record exists in the database, 
        it should return a default UserPreference object.
        """
        pass
    
    @abstractmethod
    def save(self, preference: UserPreference) -> None:
        pass


class NotificationRepository(ABC):
    @abstractmethod
    def save(self, notification: Notification) -> None:
        pass
    
    @abstractmethod
    def get_by_provider_message_id(self, provider_message_id: str) -> Optional[Notification]:
        pass

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Optional[Notification]:
        pass
    
    @abstractmethod
    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        pass
    
    @abstractmethod
    def get_all_scheduled(self) -> list[Notification]:
        """Fetches all notifications waiting to be fired."""
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
    def commit_notification(self, notification: Notification) -> None:
        pass

    @abstractmethod
    def commit_notification_and_outbox(
        self, notification: Notification, outbox_event: OutboxEvent
    ) -> None:
        pass
