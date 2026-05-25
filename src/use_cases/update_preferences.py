import logging
from dataclasses import dataclass
from typing import List
from src.interfaces.repositories import UserPreferenceRepository
from src.infrastructure.observability.logger import configure_json_logging


configure_json_logging()

logger = logging.getLogger(__name__)


@dataclass
class UpdatePreferencesRequest:
    user_id: str
    unsubscribed_channels: List[str]


class UpdatePreferencesUseCase:
    def __init__(self, user_preference_repo: UserPreferenceRepository):
        self.user_preference_repo = user_preference_repo

    def execute(self, request: UpdatePreferencesRequest) -> None:
        preferences = self.user_preference_repo.get_by_user_id(request.user_id)
        preferences.unsubscribed_channels = request.unsubscribed_channels
        
        self.user_preference_repo.save(preferences)
        logger.info(f"Updated preferences for user {request.user_id}: {request.unsubscribed_channels}")