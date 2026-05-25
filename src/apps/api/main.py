from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.apps.api.routers import notifications, webhooks, preferences
from src.apps.api.core.exceptions import setup_exception_handlers
from src.infrastructure.observability.logger import configure_json_logging
from src.apps.api.core.middleware import ObservabilityMiddleware


configure_json_logging()

app = FastAPI(title="Notification Platform API")

setup_exception_handlers(app)

app.add_middleware(ObservabilityMiddleware)


@app.get("/health", tags=["Health Check"])
def health_check():
    """A health probe to verify the API is running."""
    return {
        "status": "healthy",
        "service": "notification-platform"
    }


@app.get("/metrics", include_in_schema=False)
def get_metrics():
    """
    Prometheus will scrape this endpoint every 15 seconds.
    It returns the raw metric string payload.
    """
    return PlainTextResponse(
        generate_latest(), 
        media_type=CONTENT_TYPE_LATEST
    )


# Route registration
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(preferences.router, prefix="/api/v1/preferences", tags=["Preferences"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])