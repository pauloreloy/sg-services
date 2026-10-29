"""Port for reading step status records from DynamoDB."""

from __future__ import annotations

from typing import Protocol

from app.domain.models import StepStatusRecord


class StepStatusRepositoryPort(Protocol):
    """Abstract port for step status queries."""

    async def find_step_status(
        self, request_id: str, step_name: str, attempt_id: str | None = None
    ) -> StepStatusRecord | None:
        """Find the step status for a given request, step name, and optional attempt."""
        ...
