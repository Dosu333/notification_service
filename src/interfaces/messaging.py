from abc import ABC, abstractmethod
from typing import Dict, Any


class MessageBroker(ABC):
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publishes an event to the queue with the given topic and payload."""
        pass