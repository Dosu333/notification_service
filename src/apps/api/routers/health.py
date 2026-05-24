from fastapi import APIRouter, status

router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
def health_check():
    """A health probe to verify the API is running."""
    return {
        "status": "healthy",
        "service": "notification-platform"
    }