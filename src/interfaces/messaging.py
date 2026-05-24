from abc import ABC, abstractmethod
from typing import Dict, Any, Callable


class MessageBroker(ABC):
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publishes an event to the queue (e.g., Redpanda/Kafka)"""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Blocks until all queued messages are delivered to the broker."""
        pass


class MessageConsumer(ABC):
    @abstractmethod
    def start_consuming(
        self, 
        topic: str, 
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Continuously polls the given topic for new messages.
        
        Args:
            topic: The name of the queue/topic to read from.
            handler: A function that takes the parsed JSON payload.
        """
        pass