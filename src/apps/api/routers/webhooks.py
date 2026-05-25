import logging
from fastapi import APIRouter, Request, Response, status, Depends, Form
from typing import Optional
from src.apps.api.core.dependencies import get_webhook_use_case
from src.apps.api.core.security import verify_twilio_signature, verify_mailgun_signature
from src.use_cases.handle_delivery_receipt import (
    HandleDeliveryReceiptUseCase,
    DeliveryReceiptDTO
)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/twilio", dependencies=[Depends(verify_twilio_signature)])
async def twilio_webhook(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    ErrorCode: Optional[str] = Form(None),
    use_case: HandleDeliveryReceiptUseCase = Depends(get_webhook_use_case)
):
    domain_status = "SENT"
    if MessageStatus in ["delivered"]:
        domain_status = "DELIVERED"
    elif MessageStatus in ["failed", "undelivered"]:
        domain_status = "FAILED"

    receipt = DeliveryReceiptDTO(
        provider_message_id=MessageSid,
        status=domain_status,
        provider_name="TWILIO",
        error_details=f"Twilio Error Code: {ErrorCode}" if ErrorCode else ""
    )
    
    use_case.execute(receipt)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/mailgun", dependencies=[Depends(verify_mailgun_signature)])
async def mailgun_webhook(
    request: Request,
    use_case: HandleDeliveryReceiptUseCase = Depends(get_webhook_use_case)
):
    payload = await request.json()
    event_data = payload.get("event-data", {})

    message_id = event_data.get("message", {}).get("headers", {}).get("message-id", "")
    event_type = event_data.get("event", "")

    domain_status = "SENT"
    if event_type == "delivered":
        domain_status = "DELIVERED"
    elif event_type in ["failed", "rejected", "bounced"]:
        domain_status = "FAILED"

    receipt = DeliveryReceiptDTO(
        provider_message_id=message_id,
        status=domain_status,
        provider_name="MAILGUN",
        error_details=str(event_data.get("delivery-status", {}).get("message", ""))
    )

    use_case.execute(receipt)
    return Response(status_code=status.HTTP_200_OK)
