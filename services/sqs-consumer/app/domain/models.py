"""Core domain entities and value objects.

This module is intentionally free of any framework or AWS SDK dependency,
following the hexagonal architecture principle that the domain must not know
about the outside world.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import ProcessingStatus
from app.domain.exceptions import InvalidMessagePayloadError

ACTION_KEY = "action"
FAILURE_ACTION_VALUE = "fail"
GRANT_ID_KEY = "grant_id"


@dataclass(frozen=True)
class IncomingMessage:
    """Represents a message received from the source queue (sg-share-queue)."""

    message_id: str
    receipt_handle: str
    payload: Mapping[str, Any]

    @property
    def action(self) -> str | None:
        """Return the raw ``action`` value contained in the payload, if any."""
        value = self.payload.get(ACTION_KEY)
        return str(value) if value is not None else None

    @property
    def grant_id(self) -> str | None:
        """Return the raw ``grant_id`` value contained in the payload, if any."""
        value = self.payload.get(GRANT_ID_KEY)
        return str(value) if value is not None else None

    def ensure_has_action(self) -> str:
        """Validate that the payload contains a usable ``action`` key.

        Returns the normalized (lower-case, trimmed) action value.
        Raises ``InvalidMessagePayloadError`` when the key is missing or empty.
        """
        action = self.action
        if action is None or not action.strip():
            raise InvalidMessagePayloadError(
                f"Message '{self.message_id}' payload is missing the required "
                f"'{ACTION_KEY}' key."
            )
        return action.strip().lower()


@dataclass(frozen=True)
class ProcessingRecord:
    """Represents the audit record persisted for every processed message.

    One record is always created regardless of whether the business outcome
    was a success or a failure.
    """

    message_id: str
    action: str
    status: ProcessingStatus
    payload: Mapping[str, Any]
    reason: str | None = None
    grant_id: str | None = None
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    processed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def success(cls, message: IncomingMessage, action: str) -> ProcessingRecord:
        return cls(
            message_id=message.message_id,
            action=action,
            status=ProcessingStatus.SUCCESS,
            payload=message.payload,
            reason=None,
            grant_id=message.grant_id,
        )

    @classmethod
    def failure(
        cls, message: IncomingMessage, action: str | None, reason: str
    ) -> ProcessingRecord:
        return cls(
            message_id=message.message_id,
            action=action or "unknown",
            status=ProcessingStatus.FAILURE,
            payload=message.payload,
            reason=reason,
            grant_id=message.grant_id,
        )

    @property
    def is_success(self) -> bool:
        return self.status is ProcessingStatus.SUCCESS
