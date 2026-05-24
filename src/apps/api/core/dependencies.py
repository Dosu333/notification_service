import os
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository, SqlAlchemyUnitOfWork
from src.use_cases.create_notification import CreateNotificationUseCase
from src.use_cases.handle_delivery_receipt import HandleDeliveryReceiptUseCase


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