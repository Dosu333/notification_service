from fastapi import FastAPI
from src.apps.api.routers import notifications
from src.apps.api.core.exceptions import setup_exception_handlers

app = FastAPI(title="Notification Platform API")

setup_exception_handlers(app)

# Route registration
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])