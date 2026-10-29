"""API schemas for intake service."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IntakeRequestSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str | None = Field(None, alias="requestId")
    attempt_id: str | None = Field(None, alias="attemptId")
    correlation_id: str | None = Field(None, alias="correlationId")

    producer_account_id: str | None = Field(None, alias="producerAccountId")
    consumer_account_id: str | None = Field(None, alias="consumerAccountId")
    database_name: str | None = Field(None, alias="databaseName")
    table_names: list[str] = Field(default_factory=list, alias="tableNames")
    iam_principal_arn: str | None = Field(None, alias="iamPrincipalArn")
    permissions: list[str] = Field(default_factory=lambda: ["DESCRIBE", "SELECT"])

    # Optional S3 pointer (Account A pattern from architecture diagram)
    s3_bucket: str | None = Field(None, alias="s3Bucket")
    s3_key: str | None = Field(None, alias="s3Key")

    # Simulation knobs
    action: str = "success"
    fail_at_step: str | None = Field(None, alias="failAtStep")


class IntakeResponseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    request_id: str = Field(..., alias="requestId")
    attempt_id: str = Field(..., alias="attemptId")
    correlation_id: str = Field(..., alias="correlationId")
    status: str


class HealthResponse(BaseModel):
    status: str
    app_name: str
