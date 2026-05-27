from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from src.apps.api.schemas.requests import CreateNotificationSchema 
from src.apps.api.core.dependencies import get_create_notification_use_case
from src.use_cases.create_notification import CreateNotificationUseCase, CreateNotificationRequest
from src.use_cases.cancel_notification import CancelNotificationUseCase
from src.apps.api.core.dependencies import get_cancel_notification_use_case
from src.infrastructure.redis.rate_limiter import RedisRateLimiter
from src.apps.api.core.dependencies import get_rate_limiter


router = APIRouter()


def rate_limit_ip(request: Request, limiter: RedisRateLimiter = Depends(get_rate_limiter)):
    client_ip = request.client.host or "unknown"
    allowed, remaining = limiter.is_allowed(f"ip:{client_ip}", limit=100, window_seconds=60)
    
    if not allowed:
        raise HTTPException(
            status_code=429, 
            detail="Too Many Requests",
            headers={"Retry-After": "60"}
        )


@router.post("/", status_code=status.HTTP_200_OK, dependencies=[Depends(rate_limit_ip)])
def create_notification(
    request_body: CreateNotificationSchema,
    use_case: CreateNotificationUseCase = Depends(get_create_notification_use_case)
):
    app_request = CreateNotificationRequest(
        user_id=request_body.user_id,
        channel=request_body.channel,
        payload=request_body.payload,
        idempotency_key=request_body.idempotency_key,
        template=request_body.template,
        scheduled_at=request_body.scheduled_at,
        recurrence_rule=request_body.recurrence_rule,
        timezone=request_body.timezone
    )

    response = use_case.execute(app_request)

    return JSONResponse(
        content={
            "success": response.success,
            "status": response.status.value,
            "message": response.message,
            "notification_id": (
                str(response.notification_id)
                if response.notification_id else None
            )
        },
        status_code=status.HTTP_200_OK
    )


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
def cancel_scheduled_notification(
    notification_id: str,
    use_case: CancelNotificationUseCase = Depends(get_cancel_notification_use_case)
):
    success = use_case.execute(notification_id)
    
    if success:
        return {"success": True, "message": "Notification successfully cancelled."}
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "message": "Notification not found or cannot be cancelled."}
    )
