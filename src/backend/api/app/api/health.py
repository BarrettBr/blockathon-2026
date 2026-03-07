"""Health check router."""

from fastapi import APIRouter

from app.config.settings import settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Basic API liveness endpoint."""
    return {"status": "ok", "service": settings.APP_NAME}
