"""Domain models for diagnostic service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TerminalEventMessage:
    message_id: str
    receipt_handle: str
    payload: Mapping[str, Any]

    @property
    def request_id(self) -> str:
        return str(self.payload.get("requestId") or self.payload.get("request_id") or "")

    @property
    def attempt_id(self) -> str:
        return str(self.payload.get("attemptId") or self.payload.get("attempt_id") or "attempt-0001")

    @property
    def correlation_id(self) -> str:
        return str(self.payload.get("correlationId") or self.payload.get("correlation_id") or "")

    @property
    def terminal_status(self) -> str:
        return str(self.payload.get("terminalStatus") or self.payload.get("terminal_status") or "UNKNOWN")

    @property
    def failed_step(self) -> str | None:
        val = self.payload.get("failedStep") or self.payload.get("failed_step")
        return str(val) if val else None

    @property
    def error_code(self) -> str | None:
        val = self.payload.get("errorCode") or self.payload.get("error_code")
        return str(val) if val else None

    @property
    def message(self) -> str | None:
        val = self.payload.get("message")
        return str(val) if val else None


@dataclass(frozen=True)
class DiagnosticOutcome:
    request_id: str
    attempt_id: str
    terminal_status: str
    steps_evaluated: list[dict[str, Any]]
    first_failed_step: str | None = None
    step_functions_execution_arn: str | None = None
    sns_published: bool = False
