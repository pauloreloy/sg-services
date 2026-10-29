"""Application DTOs for intake service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeResult:
    request_id: str
    attempt_id: str
    correlation_id: str
    status: str
