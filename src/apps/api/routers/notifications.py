from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from src.apps.api.schemas.requests import CreateNotificationSchema 
from src.apps.api.core.dependencies import get_create_notification_use_case
from src.use_cases.create_notification import CreateNotificationUseCase, CreateNotificationRequest


router = APIRouter()


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def create_notification(
    request_body: CreateNotificationSchema,
    use_case: CreateNotificationUseCase = Depends(get_create_notification_use_case)
):
    app_request = CreateNotificationRequest(
        user_id=request_body.user_id,
        channel=request_body.channel,
        payload=request_body.payload,
        idempotency_key=request_body.idempotency_key,
        template=request_body.template
    )

    response = use_case.execute(app_request)

    return JSONResponse(
        content={
            "success": response.success,
            "message": response.message,
            "notification_id": (
                str(response.notification_id)
                if response.notification_id else None
            )
        },
        status_code=(
            status.HTTP_200_OK
            if "already processed" in response.message
            else status.HTTP_202_ACCEPTED
        )
    )