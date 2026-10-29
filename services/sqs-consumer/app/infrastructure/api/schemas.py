"""Response schemas for the HTTP API (health/readiness endpoints)."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str


class ReadinessResponse(BaseModel):
    status: str
    worker_running: bool
