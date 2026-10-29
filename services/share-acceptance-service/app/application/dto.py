"""Application DTOs."""

from dataclasses import dataclass

from app.domain.enums import StepStatus


@dataclass(frozen=True)
class ProcessStepResult:
    message_id: str
    request_id: str
    status: StepStatus
    error_code: str | None = None
