"""Use case: retrieve the latest processing status for a grant_id.

Business rule
-------------
Given a ``grant_id``, return the most recent processing outcome
(``SUCCESS``/``FAILURE``) that was persisted by the sqs-consumer service.
If no record exists for that grant_id, :class:`GrantNotFoundError` is raised
and translated by the inbound (HTTP) adapter into a 404 response.
"""

from __future__ import annotations

import logging

from app.application.dto import CheckStepResult
from app.domain.exceptions import GrantNotFoundError
from app.domain.ports import GrantStatusRepositoryPort

logger = logging.getLogger(__name__)


class GetGrantStatusUseCase:
    """Orchestrates the lookup of a grant's latest processing status."""

    def __init__(self, repository: GrantStatusRepositoryPort) -> None:
        self._repository = repository

    async def execute(self, grant_id: str) -> CheckStepResult:
        grant_status = await self._repository.find_latest_by_grant_id(grant_id)
        if grant_status is None:
            logger.info("No record found for grant_id=%s", grant_id)
            raise GrantNotFoundError(grant_id)

        logger.info(
            "Found status=%s for grant_id=%s (record_id=%s)",
            grant_status.status.value,
            grant_id,
            grant_status.record_id,
        )
        return CheckStepResult(
            grant_id=grant_status.grant_id,
            status=grant_status.status,
            action=grant_status.action,
            reason=grant_status.reason,
            record_id=grant_status.record_id,
            message_id=grant_status.message_id,
            processed_at=grant_status.processed_at,
        )
