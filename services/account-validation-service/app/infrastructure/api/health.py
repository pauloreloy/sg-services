"""Health and readiness router."""

from fastapi import APIRouter

from app.infrastructure.api.schemas import HealthResponse
from app.infrastructure.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app_name=settings.app_name)


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ready", app_name=settings.app_name)
