"""Health/readiness HTTP routes.

These do not belong to the domain; they exist purely so the service exposes
an HTTP surface (as requested) on top of the background SQS consumer.
"""

from fastapi import APIRouter, Request

from app.infrastructure.api.schemas import HealthResponse, ReadinessResponse
from app.infrastructure.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app_name=settings.app_name)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(request: Request) -> ReadinessResponse:
    container = request.app.state.container
    worker_running = container.worker.is_running
    return ReadinessResponse(
        status="ok" if worker_running else "degraded",
        worker_running=worker_running,
    )
