# src/use_cases/update_preferences.py
import logging
from dataclasses import dataclass
from typing import Dict
from src.interfaces.repositories import UserPreferenceRepository
from src.interfaces.providers import UserPreferenceProvider


logger = logging.getLogger(__name__)


@dataclass
class UpdatePreferencesRequest:
    user_id: str
    dnd: bool
    channels: Dict[str, bool]
    templates: Dict[str, bool]


class UpdatePreferencesUseCase:
    def __init__(
        self, 
        user_preference_repo: UserPreferenceRepository,
        preference_provider: UserPreferenceProvider 
    ):
        self.user_preference_repo = user_preference_repo
        self.preference_provider = preference_provider

    def execute(self, request: UpdatePreferencesRequest) -> None:
        preferences = self.user_preference_repo.get_by_user_id(request.user_id)
        
        preferences.dnd = request.dnd
        preferences.channels = request.channels
        preferences.templates = request.templates
        
        self.user_preference_repo.save(preferences)
        logger.info(f"Updated preferences in DB for user {request.user_id}")
        
        self.preference_provider.invalidate_cache(request.user_id)
        logger.info(f"Invalidated cache for user {request.user_id} in preference provider")
