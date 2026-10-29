"""Request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ProcessingStatus


class CheckStepRequest(BaseModel):
    """Body expected by POST /checkStep."""

    grant_id: str = Field(..., min_length=1, description="Identifier of the grant to look up.")


class CheckStepResponse(BaseModel):
    """Body returned by POST /checkStep when the grant_id is found."""

    grant_id: str
    status: ProcessingStatus
    action: str
    reason: str | None
    record_id: str
    message_id: str
    processed_at: datetime


class HealthResponse(BaseModel):
    status: str
    app_name: str


class ErrorResponse(BaseModel):
    detail: str
