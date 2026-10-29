"""Domain models for intake service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class GovernanceRequest:
    producer_account_id: str
    consumer_account_id: str
    database_name: str
    table_names: list[str]
    iam_principal_arn: str
    permissions: list[str] = field(default_factory=lambda: ["DESCRIBE", "SELECT"])
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    attempt_id: str = "attempt-0001"
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:8]}")
    s3_bucket: str | None = None
    s3_key: str | None = None
    action: str = "success"
    fail_at_step: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_payload_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "attemptId": self.attempt_id,
            "correlationId": self.correlation_id,
            "producer_account_id": self.producer_account_id,
            "consumer_account_id": self.consumer_account_id,
            "database_name": self.database_name,
            "table_names": self.table_names,
            "iam_principal_arn": self.iam_principal_arn,
            "permissions": self.permissions,
            "s3_bucket": self.s3_bucket,
            "s3_key": self.s3_key,
            "action": self.action,
            "fail_at_step": self.fail_at_step,
            "created_at": self.created_at,
        }
