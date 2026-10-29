"""Core domain entities for the checkStep service.

Framework/AWS-free, following hexagonal architecture principles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import ProcessingStatus


@dataclass(frozen=True)
class GrantStatus:
    """The latest known processing outcome for a given grant_id."""

    grant_id: str
    record_id: str
    message_id: str
    action: str
    status: ProcessingStatus
    processed_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class StepStatusRecord:
    """Represents the status of a specific choreographic step as defined in ADR 5.5 / 6.2."""

    request_id: str
    attempt_id: str
    step_name: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    message: str | None = None
