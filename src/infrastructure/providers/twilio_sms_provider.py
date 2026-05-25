import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)
from src.interfaces.providers import SMSProvider, ProviderError


logger = logging.getLogger(__name__)


def is_retryable_twilio_error(exception: Exception) -> bool:
    """
    Evaluates if the error is transient. 
    Only retries on 429 (Rate Limit) or 5xx (Server Down).
    Ignores 400s (e.g., Invalid Phone Number).
    """
    if isinstance(exception, TwilioRestException):
        if exception.status == 429 or exception.status >= 500:
            logger.warning(f"Transient Twilio Error {exception.status}. Triggering backoff...")
            return True
    return False


class TwilioSMSProvider(SMSProvider):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        # Initialize Twilio SDK client
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(is_retryable_twilio_error),
        reraise=True
    )
    def _execute_send_with_backoff(self, phone_number: str, message: str) -> str:
        """The actual method that interacts with Twilio's API.
        This method is wrapped with a retry decorator to handle transient errors."""
        response = self.client.messages.create(
            body=message,
            from_=self.from_number,
            to=phone_number
        )
        return response.sid

    def send(self, phone_number: str, message: str) -> str:
        """
        Public method to send an SMS.
        """
        try:
            return self._execute_send_with_backoff(phone_number, message)
            
        except TwilioRestException as e:
            # Translate infrastructure errors to business errors
            logger.error(f"Twilio API Error after retries exhausted: {e.msg} (Status: {e.status})")
            raise ProviderError(
                message=f"Twilio failed to send SMS: {e.msg}",
                provider_name="TWILIO",
                status_code=e.status
            ) from e
            
        except Exception as e:
            logger.error(f"Unexpected error in Twilio provider: {e}")
            raise ProviderError(
                message=f"Unexpected SMS failure: {str(e)}",
                provider_name="TWILIO"
            ) from e