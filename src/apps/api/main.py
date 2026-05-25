from fastapi import FastAPI
from src.apps.api.routers import notifications, webhooks, health, preferences
from src.apps.api.core.exceptions import setup_exception_handlers

app = FastAPI(title="Notification Platform API")

setup_exception_handlers(app)

# Route registration
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(health.router, prefix="/health", tags=["Health Check"])