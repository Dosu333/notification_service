import uuid
from src.interfaces.repositories import NotificationRepository, UnitOfWork


class CancelNotificationUseCase:
    def __init__(self, repo: NotificationRepository, unit_of_work: UnitOfWork):
        self.repo = repo
        self.unit_of_work = unit_of_work

    def execute(self, notification_id_str: str) -> bool:
        notification_id = uuid.UUID(notification_id_str)
        notification = self.repo.get_by_id(notification_id)

        if not notification:
            return False

        if notification.cancel():
            self.unit_of_work.commit_notification(notification)
            return True
            
        return False
