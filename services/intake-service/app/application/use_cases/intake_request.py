"""Use case: intake new governance requests and start choreographic workflow."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto import IntakeResult
from app.domain.models import GovernanceRequest
from app.domain.ports import PayloadStoragePort, QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class IntakeRequestUseCase:
    """Validates initial contract, fetches S3 payload if needed, records META, and publishes to access-validation queue."""

    def __init__(
        self,
        repository: StepRepositoryPort,
        publisher: QueuePublisherPort,
        storage: PayloadStoragePort | None = None,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._storage = storage

    async def execute(self, request: GovernanceRequest) -> IntakeResult:
        payload_dict = request.to_payload_dict()
        request_id = request.request_id
        attempt_id = request.attempt_id
        correlation_id = request.correlation_id

        # If payload is stored in S3 (as in AWS Account A from the architecture diagram), fetch it
        if request.s3_bucket and request.s3_key and self._storage:
            logger.info("Fetching payload from S3: s3://%s/%s", request.s3_bucket, request.s3_key)
            try:
                remote_payload = await self._storage.get_payload(request.s3_bucket, request.s3_key)
                # Merge remote payload
                for k, v in remote_payload.items():
                    if k not in payload_dict or not payload_dict[k]:
                        payload_dict[k] = v
                if remote_payload.get("requestId"):
                    request_id = remote_payload["requestId"]
                    payload_dict["requestId"] = request_id
                if remote_payload.get("attemptId"):
                    attempt_id = remote_payload["attemptId"]
                    payload_dict["attemptId"] = attempt_id
                if remote_payload.get("correlationId"):
                    correlation_id = remote_payload["correlationId"]
                    payload_dict["correlationId"] = correlation_id
            except Exception as exc:
                logger.warning(
                    "Could not fetch payload from S3 s3://%s/%s (%s). Falling back to inline payload.",
                    request.s3_bucket,
                    request.s3_key,
                    exc,
                )
                if not payload_dict.get("producer_account_id") and not payload_dict.get("database_name"):
                    raise ValueError(
                        f"Failed to fetch S3 payload and inline request is missing required fields: {exc}"
                    ) from exc

        # 1. Persist initial META state as RUNNING
        await self._repository.save_meta(
            request_id=request_id,
            attempt_id=attempt_id,
            status="RUNNING",
            correlation_id=correlation_id,
            payload=payload_dict,
        )

        # 2. Publish initial event to access-validation queue
        initial_event = {
            "eventType": "GovernanceRequestAccepted",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "stepName": "ACCOUNT_VALIDATION",
            "status": "RUNNING",
            "occurredAt": datetime.now(UTC).isoformat(),
            "payload": payload_dict,
        }
        await self._publisher.publish(initial_event)

        logger.info(
            "Intake accepted requestId=%s attemptId=%s",
            request_id,
            attempt_id,
        )
        return IntakeResult(
            request_id=request_id,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            status="ACCEPTED",
        )
