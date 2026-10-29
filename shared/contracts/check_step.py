"""Pydantic schemas for checkStep endpoint according to ADR Section 6.2."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CheckStepRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str | None = Field(None, alias="requestId")
    attempt_id: str | None = Field(None, alias="attemptId")
    step_name: str | None = Field(None, alias="stepName")
    # Legacy compatibility:
    grant_id: str | None = None


class CheckStepResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    request_id: str | None = Field(None, alias="requestId")
    attempt_id: str | None = Field(None, alias="attemptId")
    step_name: str | None = Field(None, alias="stepName")
    status: str
    started_at: str | None = Field(None, alias="startedAt")
    completed_at: str | None = Field(None, alias="completedAt")
    error_code: str | None = Field(None, alias="errorCode")
    message: str | None = None

    # Legacy fields for checkstep-service compatibility:
    grant_id: str | None = None
    action: str | None = None
    reason: str | None = None
    record_id: str | None = None
    message_id: str | None = None
    processed_at: str | None = None
