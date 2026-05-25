import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class UserPreference:
    user_id: str
    unsubscribed_channels: List[str] = field(default_factory=list)

    def is_unsubscribed(self, channel: str) -> bool:
        return channel in self.unsubscribed_channels
    

@dataclass
class Notification:
    user_id: str
    channel: str  # 'email', 'sms', 'push'
    payload: Dict[str, Any]
    idempotency_key: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    template: Optional[str] = None
    status: str = "PENDING"
    provider_name: Optional[str] = None
    provider_message_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_as_sent(self, provider_name: str, provider_message_id: Optional[str] = None):
        self.status = "SENT"
        self.provider_name = provider_name
        self.provider_message_id = provider_message_id
        self.sent_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self):
        """Business rule: Increment retries and mark failed"""
        self.status = "FAILED"
        self.failed_at = datetime.utcnow()
        self.retry_count += 1
        self.updated_at = datetime.utcnow()


@dataclass
class OutboxEvent:
    topic: str
    payload: Dict[str, Any]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    processed: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    def mark_as_processed(self):
        """Business rule: Mark event as processed"""
        self.processed = 1
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
