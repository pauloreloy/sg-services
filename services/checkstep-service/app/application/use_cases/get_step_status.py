"""Use case: retrieve the status of a specific step in the governance choreography."""

from __future__ import annotations

import logging

from app.domain.exceptions import StepNotFoundError
from app.domain.models import StepStatusRecord
from app.domain.ports.step_status_repository import StepStatusRepositoryPort

logger = logging.getLogger(__name__)


class GetStepStatusUseCase:
    """Retrieves step execution status according to ADR Section 6.2."""

    def __init__(self, repository: StepStatusRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self, request_id: str, step_name: str, attempt_id: str | None = None
    ) -> StepStatusRecord:
        record = await self._repository.find_step_status(
            request_id=request_id, step_name=step_name, attempt_id=attempt_id
        )
        if record is None:
            logger.info(
                "No step status found for requestId=%s stepName=%s attemptId=%s",
                request_id,
                step_name,
                attempt_id,
            )
            raise StepNotFoundError(
                f"No record found for requestId '{request_id}' and step '{step_name}'."
            )

        logger.info(
            "Found step status=%s for requestId=%s stepName=%s attemptId=%s",
            record.status,
            request_id,
            step_name,
            record.attempt_id,
        )
        return record
