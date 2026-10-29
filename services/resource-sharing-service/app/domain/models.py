"""Domain models for resource sharing service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import InvalidMessagePayloadError


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    receipt_handle: str
    payload: Mapping[str, Any]

    @property
    def request_id(self) -> str:
        req_id = self.payload.get("requestId") or self.payload.get("request_id")
        if not req_id:
            raise InvalidMessagePayloadError("Missing requestId in message payload.")
        return str(req_id)

    @property
    def attempt_id(self) -> str:
        return str(self.payload.get("attemptId") or self.payload.get("attempt_id") or "attempt-0001")

    @property
    def correlation_id(self) -> str:
        return str(self.payload.get("correlationId") or self.payload.get("correlation_id") or "")

    @property
    def producer_account_id(self) -> str:
        p = self.payload.get("payload", {}) if "payload" in self.payload else self.payload
        val = p.get("producer_account_id") or p.get("producerAccountId")
        return str(val) if val else ""

    @property
    def database_name(self) -> str:
        p = self.payload.get("payload", {}) if "payload" in self.payload else self.payload
        val = p.get("database_name") or p.get("databaseName")
        return str(val) if val else ""

    @property
    def action(self) -> str:
        p = self.payload.get("payload", {}) if "payload" in self.payload else self.payload
        return str(p.get("action", self.payload.get("action", "success"))).lower()

    @property
    def fail_at_step(self) -> str | None:
        p = self.payload.get("payload", {}) if "payload" in self.payload else self.payload
        val = p.get("fail_at_step") or self.payload.get("fail_at_step")
        return str(val) if val else None

    @property
    def inner_payload(self) -> dict[str, Any]:
        if "payload" in self.payload and isinstance(self.payload["payload"], dict):
            return dict(self.payload["payload"])
        return dict(self.payload)
