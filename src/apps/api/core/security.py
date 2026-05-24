import os
import hmac
import hashlib
import logging
from fastapi import Request, HTTPException, status
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
load_dotenv()


async def verify_twilio_signature(request: Request) -> None:
    """
    FastAPI Dependency: Validates the X-Twilio-Signature header.
    Throws a 403 Forbidden if the signature is invalid or missing.
    """
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    validator = RequestValidator(twilio_auth_token)

    signature = request.headers.get("X-Twilio-Signature", "")
    
    url = str(request.url)
    
    form_data = await request.form()

    if not validator.validate(url, form_data, signature):
        logger.warning(f"SECURITY ALERT: Invalid Twilio Webhook Signature detected from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid Twilio signature."
        )


async def verify_mailgun_signature(request: Request) -> None:
    """
    FastAPI Dependency: Validates the Mailgun HMAC-SHA256 signature.
    Throws a 403 Forbidden if the signature is invalid or missing.
    """
    signing_key = os.environ.get("MAILGUN_SIGNING_KEY", os.environ.get("MAILGUN_API_KEY", "")).encode('utf-8')

    try:
        body = await request.json()
        sig_data = body.get("signature", {})
        
        timestamp = sig_data.get("timestamp")
        token = sig_data.get("token")
        provided_signature = sig_data.get("signature")

        if not all([timestamp, token, provided_signature]):
            raise ValueError("Missing signature fields.")

        message = f"{timestamp}{token}".encode('utf-8')
        expected_signature = hmac.new(signing_key, message, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("Signature mismatch.")

    except Exception as e:
        logger.warning(f"SECURITY ALERT: Invalid Mailgun Webhook Signature detected. Reason: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid Mailgun signature."
        )
