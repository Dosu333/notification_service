from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class CreateNotificationSchema(BaseModel):
    user_id: str = Field(..., description="The unique ID of the recipient user.")
    channel: str = Field(..., description="The delivery channel (e.g., 'email', 'sms', 'push').")
    payload: Dict[str, Any] = Field(..., description="The dynamic data for the template.")
    idempotency_key: str = Field(..., description="A unique key to prevent duplicate processing.")
    template: Optional[str] = Field(None, description="Optional template identifier.")