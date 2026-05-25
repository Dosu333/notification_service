import uuid
import pytz
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from croniter import croniter


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
    
    def process_scheduling(self, reference_time: datetime = None) -> bool:
        """
        Determines if the notification should be rescheduled 
        or marked as ready for immediate delivery.
        Returns True if rescheduled, False if it was a one-off.
        """
        if not self.recurrence_rule:
            self.status = "PENDING"
            self.updated_at = datetime.utcnow()
            return False

        if reference_time is None:
            reference_time = datetime.utcnow()

        tz = pytz.timezone(self.timezone)
        localized_ref = pytz.utc.localize(reference_time).astimezone(tz)

        try:
            cron = croniter(self.recurrence_rule, localized_ref)
            next_time_local = cron.get_next(datetime)
            next_time_utc = next_time_local.astimezone(pytz.utc).replace(tzinfo=None)
            
            self.scheduled_at = next_time_utc
            self.status = "SCHEDULED"
            self.updated_at = datetime.utcnow()
            return True
            
        except (ValueError, KeyError):
            self.status = "PENDING"
            self.updated_at = datetime.utcnow()
            return False
    
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
