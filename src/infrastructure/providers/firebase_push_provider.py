import logging
from typing import Dict, Optional
import firebase_admin
from firebase_admin import credentials, messaging, exceptions
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)
from src.interfaces.providers import PushProvider, ProviderError
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()

logger = logging.getLogger(__name__)


def is_retryable_fcm_error(exception: Exception) -> bool:
    """
    Retries on transient FCM errors like rate limits or internal server errors.
    Ignores 400s (e.g., Unregistered Device Token).
    """
    if isinstance(exception, exceptions.FirebaseError):
        if exception.http_response and exception.http_response.status_code in [429, 500, 503, 504]:
            logger.warning(f"Transient FCM Error {exception.code}. Retrying...")
            return True
    return False


class FirebasePushProvider(PushProvider):
    def __init__(self, service_account_path: str):
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(is_retryable_fcm_error),
        reraise=True
    )
    def _execute_send_with_backoff(self, message: messaging.Message) -> str:
        """Executes the outbound request to Google FCM."""
        return messaging.send(message)

    def send(
        self, 
        device_token: str, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, str]] = None
    ) -> str:
        
        if not device_token:
            raise ProviderError("Missing device_token for push notification.", "FCM")

        fcm_message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=device_token,
        )

        try:
            return self._execute_send_with_backoff(fcm_message)
            
        except exceptions.NotFoundError as e:
            logger.error(f"FCM Token Unregistered: {e}")
            raise ProviderError(
                message=f"Device token unregistered: {e}",
                provider_name="FCM",
                status_code=404
            ) from e
            
        except exceptions.FirebaseError as e:
            logger.error(f"FCM API Error after retries exhausted: {e}")
            status_code = e.http_response.status_code if e.http_response else 500
            raise ProviderError(
                message=f"FCM failed to send Push: {e}",
                provider_name="FCM",
                status_code=status_code
            ) from e
