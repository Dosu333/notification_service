# src/apps/api/routers/preferences.py
from fastapi import APIRouter, Depends, status, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict
from src.apps.api.core.dependencies import get_update_preferences_use_case
from src.use_cases.update_preferences import UpdatePreferencesUseCase, UpdatePreferencesRequest


router = APIRouter()


class UpdatePreferencesSchema(BaseModel):
    dnd: bool = Field(
        default=False, 
        description="Global Do-Not-Disturb toggle."
    )
    channels: Dict[str, bool] = Field(
        default_factory=dict, 
        description="Channel opt-ins/outs (e.g., {'SMS': False, 'EMAIL': True})"
    )
    templates: Dict[str, bool] = Field(
        default_factory=dict, 
        description="Template opt-ins/outs (e.g., {'marketing': False})"
    )


@router.put("/{user_id}", status_code=status.HTTP_200_OK)
def update_user_preferences(
    request_body: UpdatePreferencesSchema,
    user_id: str = Path(..., description="The ID of the user"),
    use_case: UpdatePreferencesUseCase = Depends(get_update_preferences_use_case)
):
    app_request = UpdatePreferencesRequest(
        user_id=user_id,
        dnd=request_body.dnd,
        channels=request_body.channels,
        templates=request_body.templates
    )

    use_case.execute(app_request)

    return JSONResponse(
        content={
            "success": True, 
            "message": f"Preferences updated for user {user_id}."
        },
        status_code=status.HTTP_200_OK
    )
