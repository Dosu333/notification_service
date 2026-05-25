import os
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository, SqlAlchemyUnitOfWork
from src.use_cases.create_notification import CreateNotificationUseCase
from src.use_cases.handle_delivery_receipt import HandleDeliveryReceiptUseCase
from src.use_cases.update_preferences import UpdatePreferencesUseCase
from src.infrastructure.database.repositories import SqlAlchemyUserPreferenceRepository
from src.use_cases.cancel_notification import CancelNotificationUseCase


load_dotenv()
engine = create_engine(os.environ.get("DATABASE_URL"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yields a database session and safely closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_create_notification_use_case(db = Depends(get_db)) -> CreateNotificationUseCase:
    """Assembles the Use Case with its infrastructure dependencies."""
    repo = SqlAlchemyNotificationRepository(db)
    uow = SqlAlchemyUnitOfWork(db)
    return CreateNotificationUseCase(notification_repo=repo, unit_of_work=uow)


def get_webhook_use_case(db = Depends(get_db)) -> HandleDeliveryReceiptUseCase:
    """Assembles the HandleDeliveryReceiptUseCase with its concrete repository."""
    repo = SqlAlchemyNotificationRepository(db)
    return HandleDeliveryReceiptUseCase(notification_repo=repo)


def get_update_preferences_use_case(db = Depends(get_db)) -> UpdatePreferencesUseCase:
    """Assembles the UpdatePreferencesUseCase with its concrete repository."""
    repo = SqlAlchemyUserPreferenceRepository(db)
    return UpdatePreferencesUseCase(user_preference_repo=repo)


def get_cancel_notification_use_case(db = Depends(get_db)) -> CancelNotificationUseCase:
    """Assembles the CancelNotificationUseCase with its concrete repository."""
    repo = SqlAlchemyNotificationRepository(db)
    uow = SqlAlchemyUnitOfWork(db, repo)
    return CancelNotificationUseCase(notification_repo=repo, unit_of_work=uow)