"""Request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CheckStepRequest(BaseModel):
    """Body expected by POST /checkStep or POST /internal/checkStep."""

    model_config = ConfigDict(populate_by_name=True)

    # ADR fields (camelCase alias supported)
    request_id: str | None = Field(None, alias="requestId", description="Unique request identifier.")
    attempt_id: str | None = Field(None, alias="attemptId", description="Unique attempt identifier.")
    step_name: str | None = Field(None, alias="stepName", description="Step name.")

    # Legacy field
    grant_id: str | None = Field(None, description="Identifier of the grant to look up.")

    @model_validator(mode="after")
    def validate_identification(self) -> CheckStepRequest:
        if not self.grant_id and not (self.request_id and self.step_name):
            raise ValueError("Must provide either 'grant_id' or both 'requestId' and 'stepName'.")
        return self


class CheckStepResponse(BaseModel):
    """Body returned by POST /checkStep / POST /internal/checkStep."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    # ADR fields
    request_id: str | None = Field(None, alias="requestId")
    attempt_id: str | None = Field(None, alias="attemptId")
    step_name: str | None = Field(None, alias="stepName")
    status: str
    started_at: str | None = Field(None, alias="startedAt")
    completed_at: str | None = Field(None, alias="completedAt")
    error_code: str | None = Field(None, alias="errorCode")
    message: str | None = None

    # Legacy fields
    grant_id: str | None = None
    action: str | None = None
    reason: str | None = None
    record_id: str | None = None
    message_id: str | None = None
    processed_at: datetime | str | None = None


class HealthResponse(BaseModel):
    status: str
    app_name: str


class ErrorResponse(BaseModel):
    detail: str
