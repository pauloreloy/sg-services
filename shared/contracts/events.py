"""Governance workflow event models, enums and contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class StepName(str, Enum):
    ACCOUNT_VALIDATION = "ACCOUNT_VALIDATION"
    CATALOG_VALIDATION = "CATALOG_VALIDATION"
    RESOURCE_SHARING = "RESOURCE_SHARING"
    SHARE_ACCEPTANCE = "SHARE_ACCEPTANCE"
    RESOURCE_LINKS = "RESOURCE_LINKS"
    PERMISSIONS = "PERMISSIONS"


STEP_SEQUENCE: list[StepName] = [
    StepName.ACCOUNT_VALIDATION,
    StepName.CATALOG_VALIDATION,
    StepName.RESOURCE_SHARING,
    StepName.SHARE_ACCEPTANCE,
    StepName.RESOURCE_LINKS,
    StepName.PERMISSIONS,
]


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"


class TerminalStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class GovernancePayload:
    """Carries the business context across the choreographic pipeline."""

    request_id: str
    attempt_id: str
    correlation_id: str
    producer_account_id: str
    consumer_account_id: str
    database_name: str
    table_names: list[str]
    iam_principal_arn: str
    permissions: list[str] = field(default_factory=lambda: ["DESCRIBE", "SELECT"])
    catalog_id: str | None = None
    share_arn: str | None = None
    resource_link_name: str | None = None
    s3_payload_location: str | None = None
    action: str = "success"  # "success" or "fail" (for simulation/testing)
    fail_at_step: str | None = None  # To simulate failure at a specific step
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GovernancePayload:
        return cls(
            request_id=str(data.get("request_id") or data.get("requestId", "")),
            attempt_id=str(data.get("attempt_id") or data.get("attemptId", "attempt-0001")),
            correlation_id=str(data.get("correlation_id") or data.get("correlationId", "")),
            producer_account_id=str(data.get("producer_account_id", "")),
            consumer_account_id=str(data.get("consumer_account_id", "")),
            database_name=str(data.get("database_name", "")),
            table_names=list(data.get("table_names", [])),
            iam_principal_arn=str(data.get("iam_principal_arn", "")),
            permissions=list(data.get("permissions", ["DESCRIBE", "SELECT"])),
            catalog_id=data.get("catalog_id"),
            share_arn=data.get("share_arn"),
            resource_link_name=data.get("resource_link_name"),
            s3_payload_location=data.get("s3_payload_location"),
            action=str(data.get("action", "success")).lower(),
            fail_at_step=data.get("fail_at_step"),
            extra=dict(data.get("extra", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GovernanceEvent:
    """Event published to SQS between microservices."""

    event_type: str
    request_id: str
    attempt_id: str
    correlation_id: str
    step_name: StepName
    status: StepStatus
    payload: dict[str, Any]
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_version: int = 1
    error_code: str | None = None
    message: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GovernanceEvent:
        step_raw = data.get("step_name") or data.get("stepName", StepName.ACCOUNT_VALIDATION.value)
        status_raw = data.get("status", StepStatus.RUNNING.value)
        return cls(
            event_type=str(data.get("event_type") or data.get("eventType", "")),
            request_id=str(data.get("request_id") or data.get("requestId", "")),
            attempt_id=str(data.get("attempt_id") or data.get("attemptId", "attempt-0001")),
            correlation_id=str(data.get("correlation_id") or data.get("correlationId", "")),
            step_name=StepName(step_raw),
            status=StepStatus(status_raw),
            payload=dict(data.get("payload", {})),
            occurred_at=str(data.get("occurred_at") or data.get("occurredAt", datetime.now(UTC).isoformat())),
            event_version=int(data.get("event_version") or data.get("eventVersion", 1)),
            error_code=data.get("error_code") or data.get("errorCode"),
            message=data.get("message"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventType": self.event_type,
            "eventVersion": self.event_version,
            "requestId": self.request_id,
            "attemptId": self.attempt_id,
            "correlationId": self.correlation_id,
            "stepName": self.step_name.value,
            "status": self.status.value,
            "occurredAt": self.occurred_at,
            "errorCode": self.error_code,
            "message": self.message,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class TerminalEvent:
    """Terminal event published to workflow-completed or workflow-failed."""

    event_type: str  # "WorkflowCompleted" or "WorkflowFailed"
    request_id: str
    attempt_id: str
    correlation_id: str
    terminal_status: str  # "SUCCEEDED" or "FAILED"
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_version: int = 1
    failed_step: str | None = None
    error_code: str | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def completed(
        cls,
        request_id: str,
        attempt_id: str,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> TerminalEvent:
        return cls(
            event_type="WorkflowCompleted",
            request_id=request_id,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            terminal_status="SUCCEEDED",
            payload=payload or {},
        )

    @classmethod
    def failed(
        cls,
        request_id: str,
        attempt_id: str,
        correlation_id: str,
        failed_step: str,
        error_code: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> TerminalEvent:
        return cls(
            event_type="WorkflowFailed",
            request_id=request_id,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            terminal_status="FAILED",
            failed_step=failed_step,
            error_code=error_code,
            message=message,
            payload=payload or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventType": self.event_type,
            "eventVersion": self.event_version,
            "requestId": self.request_id,
            "attemptId": self.attempt_id,
            "correlationId": self.correlation_id,
            "terminalStatus": self.terminal_status,
            "failedStep": self.failed_step,
            "errorCode": self.error_code,
            "message": self.message,
            "occurredAt": self.occurred_at,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
