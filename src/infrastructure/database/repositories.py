import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional
from src.domain.entities import Notification, OutboxEvent,UserPreference
from src.interfaces.repositories import NotificationRepository, UnitOfWork, UserPreferenceRepository
from src.infrastructure.database.models import NotificationModel, OutboxEventModel, UserPreferenceModel


class SqlAlchemyUserPreferenceRepository(UserPreferenceRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_entity(self, model: UserPreferenceModel) -> UserPreference:
        return UserPreference(
            user_id=model.user_id,
            unsubscribed_channels=model.unsubscribed_channels
        )

    def _to_model(self, entity: UserPreference) -> UserPreferenceModel:
        return UserPreferenceModel(
            user_id=entity.user_id,
            unsubscribed_channels=entity.unsubscribed_channels
        )

    def get_by_user_id(self, user_id: str) -> UserPreference:
        model = self.session.query(UserPreferenceModel).filter_by(user_id=user_id).first()
        
        if model:
            return self._to_entity(model)
        return UserPreference(user_id=user_id, unsubscribed_channels=[])

    def save(self, preference: UserPreference) -> None:
        model = self.session.query(UserPreferenceModel).filter_by(user_id=preference.user_id).first()
        
        if model:
            model.unsubscribed_channels = preference.unsubscribed_channels
        else:
            new_model = self._to_model(preference)
            self.session.add(new_model)


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Session):
        self.session = session

    def _to_entity(self, model: NotificationModel) -> Notification:
        return Notification(
            id=model.id,
            user_id=model.user_id,
            channel=model.channel,
            payload=model.payload,
            idempotency_key=model.idempotency_key,
            template=model.template,
            status=model.status,
            retry_count=model.retry_count,
            provider_name=model.provider_name,
            provider_message_id=model.provider_message_id,
            scheduled_at=model.scheduled_at,
            recurrence_rule=model.recurrence_rule,
            timezone=model.timezone,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            failed_at=model.failed_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, entity: Notification) -> NotificationModel:
        return NotificationModel(
            id=entity.id,
            user_id=entity.user_id,
            channel=entity.channel,
            payload=entity.payload,
            idempotency_key=entity.idempotency_key,
            template=entity.template,
            status=entity.status,
            retry_count=entity.retry_count,
            provider_name=entity.provider_name,
            provider_message_id=entity.provider_message_id,
            scheduled_at=entity.scheduled_at,
            recurrence_rule=entity.recurrence_rule,
            timezone=entity.timezone,
            sent_at=entity.sent_at,
            delivered_at=entity.delivered_at,
            failed_at=entity.failed_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
        
    def save(self, notification: Notification) -> None:
        """Translates entity to model and adds it to session."""
        model = self._to_model(notification)
        self.session.add(model)

    def get_by_provider_message_id(self, provider_message_id: str) -> Optional[Notification]:
        model = self.session.query(NotificationModel).filter_by(
            provider_message_id=provider_message_id
        ).first()
        
        if model:
            return self._to_entity(model)
        return None

    def get_by_idempotency_key(self, key: str) -> Optional[Notification]:
        model = self.session.query(NotificationModel).filter_by(idempotency_key=key).first()
        
        if model:
            return self._to_entity(model)
        return None
    
    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        model = self.session.query(NotificationModel).filter_by(id=notification_id).first()
        
        if model:
            return self._to_entity(model)
        return None

    def update(self, notification: Notification) -> None:
        """Updates an existing notification"""
        self.session.query(NotificationModel).filter_by(id=notification.id).update({
            "status": notification.status,
            "provider_name": notification.provider_name,
            "scheduled_at": notification.scheduled_at,
            "recurrence_rule": notification.recurrence_rule,
            "timezone": notification.timezone,
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
    
    def commit_notification(self, notification: Notification) -> None:
        """Commits only the notification to the database."""
        try:
            model = self.notifications._to_model(notification)
            self.session.add(model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

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
