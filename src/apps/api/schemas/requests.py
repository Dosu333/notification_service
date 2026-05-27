from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime


class CreateNotificationSchema(BaseModel):
    user_id: str
    channel: str
    payload: Dict[str, Any]
    idempotency_key: str
    template: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    recurrence_rule: Optional[str] = None
    timezone: str = "UTC"
