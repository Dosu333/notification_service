from abc import ABC, abstractmethod
from typing import Dict, Optional


class MetricsService(ABC):
    """
    Abstract contract for emitting application metrics.
    """
    
    @abstractmethod
    def increment_counter(
        self, 
        metric_name: str, 
        tags: Optional[Dict[str, str]] = None, 
        value: float = 1.0
    ) -> None:
        """Records a count (e.g., total messages sent, total errors)."""
        pass

    @abstractmethod
    def record_histogram(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Records a distribution of values (e.g., API latency in seconds)."""
        pass
