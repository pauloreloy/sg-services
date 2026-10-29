"""API schemas for diagnostic service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiagnoseRequestSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., alias="requestId")
    attempt_id: str = Field("attempt-0001", alias="attemptId")
    terminal_status: str = Field("UNKNOWN", alias="terminalStatus")


class DiagnoseResponseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    request_id: str = Field(..., alias="requestId")
    attempt_id: str = Field(..., alias="attemptId")
    terminal_status: str = Field(..., alias="terminalStatus")
    steps_evaluated: list[dict[str, Any]] = Field(..., alias="stepsEvaluated")
    first_failed_step: str | None = Field(None, alias="firstFailedStep")
    step_functions_execution_arn: str | None = Field(None, alias="stepFunctionsExecutionArn")
    sns_published: bool = Field(..., alias="snsPublished")


class HealthResponse(BaseModel):
    status: str
    app_name: str
