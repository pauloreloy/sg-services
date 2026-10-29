"""Port interfaces for resource sharing service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.domain.models import IncomingMessage


class QueueConsumerPort(Protocol):
    async def receive_messages(self) -> list[IncomingMessage]: ...
    async def acknowledge(self, message: IncomingMessage) -> None: ...


class QueuePublisherPort(Protocol):
    async def publish(self, message: Mapping[str, Any]) -> None: ...


class StepRepositoryPort(Protocol):
    async def save_step(
        self,
        request_id: str,
        attempt_id: str,
        step_name: str,
        status: str,
        correlation_id: str = "",
        started_at: str | None = None,
        completed_at: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        resource_ref: dict[str, Any] | None = None,
    ) -> None: ...

    async def find_step(
        self, request_id: str, step_name: str, attempt_id: str
    ) -> dict[str, Any] | None: ...

    async def save_meta(
        self,
        request_id: str,
        attempt_id: str,
        status: str,
        correlation_id: str = "",
        payload: dict[str, Any] | None = None,
        failed_step: str | None = None,
    ) -> None: ...
