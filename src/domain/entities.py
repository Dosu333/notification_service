import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class UserPreference:
    user_id: str
    dnd: bool = False
    channels: Dict[str, bool] = field(default_factory=dict)
    templates: Dict[str, bool] = field(default_factory=dict)

    def can_receive(self, channel: str, template: Optional[str] = None) -> bool:
        """Domain logic to evaluate if a message is allowed."""
        if self.dnd:
            return False
            
        if channel.upper() in self.channels and self.channels[channel.upper()] is False:
            return False
            
        if template and template.lower() in self.templates and self.templates[template.lower()] is False:
            return False
            
        return True
        
    def to_dict(self) -> dict:
        """Helper for the Redis cache provider to serialize the entity."""
        return {
            "dnd": self.dnd,
            "channels": self.channels,
            "templates": self.templates
        }
    

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
    recurrence_rule: Optional[str] = None
    timezone: str = "UTC"
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def mark_as_scheduled(self):
        self.status = "SCHEDULED"
        self.updated_at = datetime.utcnow()

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
    
    def cancel(self) -> bool:
        """
        A notification can only be cancelled if it is currently scheduled.
        Returns True if successful, False otherwise.
        """
        if self.status == "SCHEDULED":
            self.status = "CANCELLED"
            self.updated_at = datetime.utcnow()
            return True
        return False


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
