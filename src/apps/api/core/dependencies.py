import os
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository, SqlAlchemyUnitOfWork
from src.use_cases.create_notification import CreateNotificationUseCase
from src.use_cases.handle_delivery_receipt import HandleDeliveryReceiptUseCase
from src.use_cases.update_preferences import UpdatePreferencesUseCase
from src.infrastructure.database.repositories import SqlAlchemyUserPreferenceRepository
from src.use_cases.cancel_notification import CancelNotificationUseCase
from src.infrastructure.redis.queue import RedisSchedulerQueue
from src.infrastructure.redis.preference_provider import RedisUserPreferenceProvider
from src.interfaces.providers import UserPreferenceProvider, UserQuotaProvider, IdempotencyProvider
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService
from src.infrastructure.redis.rate_limiter import RedisRateLimiter
from src.infrastructure.redis.quota_provider import RedisUserQuotaProvider
from src.infrastructure.redis.idempotency_provider import RedisIdempotencyProvider


load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(
    DATABASE_URL, 
    poolclass=NullPool
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metrics_service = PrometheusMetricsService()


def get_scheduler() -> RedisSchedulerQueue:
    """Provides a connection to the Redis Scheduler Queue."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return RedisSchedulerQueue(redis_url)


def get_db():
    """Yields a database session and safely closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_rate_limiter() -> RedisRateLimiter:
    """Provides a singleton-like connection to the Redis Rate Limiter."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return RedisRateLimiter(redis_url=redis_url)


def get_webhook_use_case(db = Depends(get_db)) -> HandleDeliveryReceiptUseCase:
    """Assembles the HandleDeliveryReceiptUseCase with its concrete repository."""
    repo = SqlAlchemyNotificationRepository(db)
    return HandleDeliveryReceiptUseCase(notification_repo=repo)


def get_preference_provider(db = Depends(get_db)) -> UserPreferenceProvider:
    """Provides the Redis preference cache layer, falling back to DB."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    db_repo = SqlAlchemyUserPreferenceRepository(db)
    return RedisUserPreferenceProvider(redis_url=redis_url, db_repo=db_repo)


def get_quota_provider() -> UserQuotaProvider:
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return RedisUserQuotaProvider(redis_url=redis_url)


def get_idempotency_provider() -> IdempotencyProvider:
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return RedisIdempotencyProvider(redis_url=redis_url)


def get_create_notification_use_case(
    db = Depends(get_db),
    scheduler = Depends(get_scheduler),
    pref_provider: UserPreferenceProvider = Depends(get_preference_provider),
    quota_provider: UserQuotaProvider = Depends(get_quota_provider),
    idempotency_provider: IdempotencyProvider = Depends(get_idempotency_provider)
) -> CreateNotificationUseCase:
    repo = SqlAlchemyNotificationRepository(db)
    uow = SqlAlchemyUnitOfWork(db)
    
    return CreateNotificationUseCase(
        notification_repo=repo,
        unit_of_work=uow,
        scheduler=scheduler,
        metrics=metrics_service,
        idempotency_provider=idempotency_provider,
        preference_provider=pref_provider,
        quota_provider=quota_provider
    )


def get_update_preferences_use_case(
    db = Depends(get_db),
    pref_provider: UserPreferenceProvider = Depends(get_preference_provider)
) -> UpdatePreferencesUseCase:
    
    repo = SqlAlchemyUserPreferenceRepository(db)
    return UpdatePreferencesUseCase(
        user_preference_repo=repo,
        preference_provider=pref_provider
    )


def get_cancel_notification_use_case(db = Depends(get_db)) -> CancelNotificationUseCase:
    """Assembles the CancelNotificationUseCase with its concrete repository."""
    repo = SqlAlchemyNotificationRepository(db)
    uow = SqlAlchemyUnitOfWork(db)
    return CancelNotificationUseCase(notification_repo=repo, unit_of_work=uow)
