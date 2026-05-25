import logging
import requests
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from src.interfaces.providers import EmailProvider, ProviderError
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()

logger = logging.getLogger(__name__)


def is_retryable_mailgun_error(exception: Exception) -> bool:
    """
    Retries only on transient network issues, rate limits (429), 
    or internal Mailgun server errors (5xx).
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        status_code = exception.response.status_code
        if status_code == 429 or status_code >= 500:
            logger.warning(f"Transient Mailgun Error {status_code}. Retrying...")
            return True
    elif isinstance(exception, requests.exceptions.ConnectionError):
        logger.warning("Mailgun connection error. Retrying...")
        return True
    return False


class MailgunEmailProvider(EmailProvider):
    def __init__(
        self,
        api_key: str,
        domain: str,
        from_email: str,
        base_url: str = "https://api.mailgun.net/v3"
    ):
        self.api_key = api_key
        self.domain = domain
        self.from_email = from_email
        self.endpoint = f"{base_url.rstrip('/')}/{domain}/messages"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(is_retryable_mailgun_error),
        reraise=True
    )
    def _execute_send_with_backoff(self, data: Dict[str, Any]) -> str:
        """Executes the HTTP POST request to Mailgun with basic authentication."""
        response = requests.post(
            self.endpoint,
            auth=("api", self.api_key),
            data=data,
            timeout=10
        )
        
        response.raise_for_status() 
        
        return response.json().get("id", "")

    def send(
        self, 
        recipient_email: str, 
        subject: str,
        body_text: str,
        template_id: Optional[str] = None, 
        template_data: Optional[Dict[str, Any]] = None
    ) -> str:
        try:
            data = {
                "from": self.from_email,
                "to": recipient_email,
                "subject": subject,
            }

            # Handle either Mailgun-hosted templates or raw body text
            if template_id:
                data["template"] = template_id
                if template_data:
                    import json
                    data["v:variables"] = json.dumps(template_data)
            else:
                data["text"] = body_text

            return self._execute_send_with_backoff(data)

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_msg = e.response.text
            logger.error(f"Mailgun API rejected request: {error_msg} (Status: {status_code})")
            raise ProviderError(
                message=f"Mailgun failed: {error_msg}",
                provider_name="MAILGUN",
                status_code=status_code
            ) from e
            
        except Exception as e:
            logger.error(f"Unexpected network or configuration failure in Mailgun provider: {e}")
            raise ProviderError(
                message=f"Unexpected Email failure: {str(e)}",
                provider_name="MAILGUN"
            ) from e
