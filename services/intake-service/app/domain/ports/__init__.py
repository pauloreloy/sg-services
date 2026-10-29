"""Port interfaces for intake service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class QueuePublisherPort(Protocol):
    async def publish(self, message: Mapping[str, Any]) -> None: ...


class StepRepositoryPort(Protocol):
    async def save_meta(
        self,
        request_id: str,
        attempt_id: str,
        status: str,
        correlation_id: str = "",
        payload: dict[str, Any] | None = None,
        failed_step: str | None = None,
    ) -> None: ...


class PayloadStoragePort(Protocol):
    async def get_payload(self, bucket: str, key: str) -> dict[str, Any]: ...
