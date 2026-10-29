"""Application layer DTOs (data transfer objects).

Kept separate from domain entities so that inbound/outbound representations
can evolve independently from the core business model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ProcessingStatus


@dataclass(frozen=True)
class ProcessMessageResult:
    """Outcome returned by :class:`ProcessMessageUseCase`."""

    message_id: str
    status: ProcessingStatus
    record_id: str
