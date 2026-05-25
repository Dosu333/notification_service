from fastapi import APIRouter, Depends, status, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List
from src.apps.api.core.dependencies import get_update_preferences_use_case
from src.use_cases.update_preferences import UpdatePreferencesUseCase, UpdatePreferencesRequest


router = APIRouter()


class UpdatePreferencesSchema(BaseModel):
    unsubscribed_channels: List[str] = Field(
        default_factory=list, 
        description="List of channels the user wishes to mute (e.g., ['sms', 'push'])"
    )
    

@router.put("/{user_id}", status_code=status.HTTP_200_OK)
def update_user_preferences(
    request_body: UpdatePreferencesSchema,
    user_id: str = Path(..., description="The ID of the user"),
    use_case: UpdatePreferencesUseCase = Depends(get_update_preferences_use_case)
):
    """
    Updates a user's notification preferences. 
    If the user does not exist in the preference database, it is automatically created.
    """
    app_request = UpdatePreferencesRequest(
        user_id=user_id,
        unsubscribed_channels=request_body.unsubscribed_channels
    )

    use_case.execute(app_request)

    return JSONResponse(
        content={
            "success": True, 
            "message": f"Preferences updated for user {user_id}."
        },
        status_code=status.HTTP_200_OK
    )
