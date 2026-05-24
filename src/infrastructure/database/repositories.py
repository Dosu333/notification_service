from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional
from src.domain.entities import Notification, OutboxEvent
from src.interfaces.repositories import NotificationRepository, UnitOfWork
from src.infrastructure.database.models import NotificationModel, OutboxEventModel


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, notification: Notification) -> None:
        """Maps  domain entity to SQLAlchemy model and adds it to session."""
        model = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            channel=notification.channel,
            template=notification.template,
            payload=notification.payload,
            status=notification.status,
            provider=notification.provider,
            idempotency_key=notification.idempotency_key,
            scheduled_at=notification.scheduled_at,
            sent_at=notification.sent_at,
            delivered_at=notification.delivered_at,
            failed_at=notification.failed_at,
            retry_count=notification.retry_count,
            created_at=notification.created_at,
            updated_at=notification.updated_at
        )
        self.session.add(model)

    def get_by_idempotency_key(self, key: str) -> Optional[Notification]:
        """Fetches DB model and maps it back to a pure domain entity."""
        model = self.session.query(NotificationModel).filter_by(idempotency_key=key).first()
        
        if not model:
            return None

        return Notification(
            id=model.id,
            user_id=model.user_id,
            channel=model.channel,
            template=model.template,
            payload=model.payload,
            status=model.status,
            provider=model.provider,
            idempotency_key=model.idempotency_key,
            scheduled_at=model.scheduled_at,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            failed_at=model.failed_at,
            retry_count=model.retry_count,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def update(self, notification: Notification) -> None:
        """Updates an existing notification"""
        self.session.query(NotificationModel).filter_by(id=notification.id).update({
            "status": notification.status,
            "provider": notification.provider,
            "sent_at": notification.sent_at,
            "failed_at": notification.failed_at,
            "delivered_at": notification.delivered_at,
            "retry_count": notification.retry_count,
            "updated_at": notification.updated_at
        })


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self.session = session
        self.notifications = SqlAlchemyNotificationRepository(session)

    def commit_notification_and_outbox(
        self, notification: Notification, outbox_event: OutboxEvent
    ) -> None:
        """
        Ensures that both the Notification and OutboxEvent are saved in the same transaction.
        """
        try:
            # Add Notification to session via the repository
            self.notifications.save(notification)
            
            # Add Outbox Event to session
            outbox_model = OutboxEventModel(
                id=outbox_event.id,
                topic=outbox_event.topic,
                payload=outbox_event.payload,
                processed=outbox_event.processed,
                created_at=outbox_event.created_at,
                processed_at=outbox_event.processed_at
            )
            self.session.add(outbox_model)
            
            # Atomic commit
            self.session.commit()
            
        except IntegrityError as e:
            self.session.rollback()
            raise e   
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e
