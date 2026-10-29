"""Application layer DTOs for the checkStep service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import ProcessingStatus


@dataclass(frozen=True)
class CheckStepResult:
    """Outcome returned by :class:`GetGrantStatusUseCase`."""

    grant_id: str
    status: ProcessingStatus
    action: str
    reason: str | None
    record_id: str
    message_id: str
    processed_at: datetime
