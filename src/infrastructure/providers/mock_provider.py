import time
import uuid
import logging
from typing import Dict, Any, Optional
from src.interfaces.providers import SMSProvider, EmailProvider, PushProvider 

logger = logging.getLogger(__name__)


class MockSMSProvider(SMSProvider):
    """
    A dummy sms provider used for local development.
    """
    def __init__(self, provider_name: str = "mock_sms_gateway"):
        self.provider_name = provider_name

    def send(self, phone_number: str, message: str) -> str:
        time.sleep(0.05) 
        
        message_id = f"mock_{uuid.uuid4()}"
        logger.debug(f"[{self.provider_name}] Simulated sending message: {message_id}")
        
        return {
            "success": True,
            "provider_message_id": message_id,
            "provider_name": self.provider_name
        }


class MockEmailProvider(EmailProvider):
    """
    A dummy email provider used for local development.
    """
    def __init__(self, provider_name: str = "mock_email_gateway"):
        self.provider_name = provider_name

    def send(
        self, 
        recipient_email: str, 
        subject: str,
        body_text: str,
        template_id: Optional[str] = None, 
        template_data: Optional[Dict[str, Any]] = None
    ) -> str:
        time.sleep(0.05) 
        
        message_id = f"mock_{uuid.uuid4()}"
        logger.debug(f"[{self.provider_name}] Simulated sending email: {message_id}")
        
        return {
            "success": True,
            "provider_message_id": message_id,
            "provider_name": self.provider_name
        }


class MockPushProvider(PushProvider):
    """
    A dummy push provider used for local development.
    """ 
    def __init__(self, provider_name: str = "mock_push_gateway"):
        self.provider_name = provider_name

    def send(
        self, 
        device_token: str, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, str]] = None
    ) -> str:
        time.sleep(0.05) 
        
        message_id = f"mock_{uuid.uuid4()}"
        logger.debug(f"[{self.provider_name}] Simulated sending push notification: {message_id}")
        
        return {
            "success": True,
            "provider_message_id": message_id,
            "provider_name": self.provider_name
        } 
