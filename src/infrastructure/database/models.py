import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class UserPreferenceModel(Base):
    __tablename__ = "user_preferences"
    user_id = Column(String, primary_key=True, index=True) 
    unsubscribed_channels = Column(JSON, default=list, nullable=False)


class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String(20), nullable=False) # 'email', 'sms', 'push'
    template = Column(String(100))
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    provider = Column(String(50))
    provider_message_id = Column(String, nullable=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    processed = Column(Integer, default=0, index=True) # 0 = false, 1 = true
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)


Index('idx_unprocessed_events', OutboxEventModel.processed, OutboxEventModel.created_at)