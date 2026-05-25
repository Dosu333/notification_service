import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from src.infrastructure.observability.logger import set_correlation_id
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.metrics_service = PrometheusMetricsService()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)
        
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
            
        except Exception as e:
            logger.error(f"Unhandled Exception in API layer: {e}")
            raise e
            
        finally:
            duration = time.perf_counter() - start_time
            
            counter_tags = {
                "method": request.method,
                "endpoint": request.url.path,
                "status": str(status_code)
            }
            histogram_tags = {
                "method": request.method,
                "endpoint": request.url.path
            }
            
            # Emit to Prometheus
            self.metrics_service.increment_counter("api_requests_total", tags=counter_tags)
            self.metrics_service.record_histogram("api_request_duration_seconds", value=duration, tags=histogram_tags)
            
            logger.info(
                f"HTTP Request Completed: {request.method} {request.url.path}",
                extra={"duration_seconds": duration, "status_code": status_code}
            )
