from typing import Optional

class NotificationScheduler:
    def schedule(self, notification_id: str, timestamp: float) -> None:
        """Pushes a notification ID and its execution time to the underlying store."""
        pass
    
    def pop_due_item(self, current_time: float) -> Optional[str]:
        """Atomically pops a due item (if any) from the underlying store."""
        pass