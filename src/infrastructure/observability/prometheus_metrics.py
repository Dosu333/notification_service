import logging
from typing import Dict, Optional
from prometheus_client import Counter, Histogram
from src.interfaces.metrics import MetricsService


logger = logging.getLogger(__name__)


class PrometheusMetricsService(MetricsService):
    """
    Concrete implementation of MetricsService.
    """
    def __init__(self):
        self._api_requests_total = Counter(
            "api_requests_total", 
            "Total HTTP requests received", 
            ["method", "endpoint", "status"]
        )
        self._api_request_duration_seconds = Histogram(
            "api_request_duration_seconds", 
            "HTTP request latency", 
            ["method", "endpoint"]
        )
        self._notifications_processed_total = Counter(
            "notifications_processed_total", 
            "Total notifications processed by workers", 
            ["channel", "status"]
        )
        self._worker_processing_duration_seconds = Histogram(
            "worker_processing_duration_seconds", 
            "Time spent processing a notification and calling providers", 
            ["channel"]
        )
        self._dlq_messages_total = Counter(
            "dlq_messages_total", 
            "Messages parked in the Dead Letter Queue", 
            ["topic", "reason"]
        )
        self._counters = {
            "api_requests_total": self._api_requests_total,
            "notifications_processed_total": self._notifications_processed_total,
            "dlq_messages_total": self._dlq_messages_total
        }
        self._histograms = {
            "api_request_duration_seconds": self._api_request_duration_seconds,
            "worker_processing_duration_seconds": self._worker_processing_duration_seconds
        }

    def increment_counter(
        self, 
        metric_name: str, 
        tags: Optional[Dict[str, str]] = None, 
        value: float = 1.0
    ) -> None:
        try:
            tags = tags or {}
            if metric_name in self._counters:
                self._counters[metric_name].labels(**tags).inc(value)
            else:
                logger.warning(f"Attempted to increment unregistered counter: {metric_name}")
        except Exception as e:
            logger.error(f"Failed to record Prometheus counter {metric_name}: {e}")

    def record_histogram(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        try:
            tags = tags or {}
            if metric_name in self._histograms:
                self._histograms[metric_name].labels(**tags).observe(value)
            else:
                logger.warning(f"Attempted to record unregistered histogram: {metric_name}")
        except Exception as e:
            logger.error(f"Failed to record Prometheus histogram {metric_name}: {e}")
