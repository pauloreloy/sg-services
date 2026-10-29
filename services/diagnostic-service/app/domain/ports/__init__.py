"""Port interfaces for diagnostic service."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models import TerminalEventMessage


class QueueConsumerPort(Protocol):
    async def receive_messages(self) -> list[TerminalEventMessage]: ...
    async def acknowledge(self, message: TerminalEventMessage) -> None: ...


class StepFunctionsInvokerPort(Protocol):
    async def start_execution(
        self, state_machine_name: str, execution_name: str, input_payload: dict[str, Any]
    ) -> str | None: ...


class CheckStepClientPort(Protocol):
    async def check_step(
        self, request_id: str, attempt_id: str, step_name: str
    ) -> dict[str, Any]: ...


class NotificationPublisherPort(Protocol):
    async def publish_notification(self, topic_name: str, message: dict[str, Any]) -> None: ...
