"""Use case: create Lake Formation / RAM resource share."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.application.dto import ProcessStepResult
from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import InvalidMessagePayloadError, ResourceSharingError
from app.domain.models import IncomingMessage
from app.domain.ports import QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class ShareResourceUseCase:
    """Coordinates resource sharing via Lake Formation/RAM, then forwards to share acceptance."""

    def __init__(
        self,
        repository: StepRepositoryPort,
        next_publisher: QueuePublisherPort,
        failure_publisher: QueuePublisherPort,
    ) -> None:
        self._repository = repository
        self._next_publisher = next_publisher
        self._failure_publisher = failure_publisher

    async def execute(self, message: IncomingMessage) -> ProcessStepResult:
        request_id = message.request_id
        attempt_id = message.attempt_id
        correlation_id = message.correlation_id
        payload = message.inner_payload

        # 1. Idempotency check
        existing = await self._repository.find_step(
            request_id=request_id,
            step_name=StepName.RESOURCE_SHARING.value,
            attempt_id=attempt_id,
        )
        if existing and existing.get("status") == StepStatus.SUCCEEDED.value:
            return ProcessStepResult(
                message_id=message.message_id,
                request_id=request_id,
                status=StepStatus.SUCCEEDED,
            )

        started_at = datetime.now(UTC).isoformat()
        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.RESOURCE_SHARING.value,
            status=StepStatus.RUNNING.value,
            correlation_id=correlation_id,
            started_at=started_at,
            payload=payload,
        )

        try:
            share_arn = self._share_resource(message)
        except (ResourceSharingError, InvalidMessagePayloadError) as exc:
            completed_at = datetime.now(UTC).isoformat()
            error_code = "RESOURCE_SHARING_ERROR"
            error_msg = str(exc)

            await self._repository.save_step(
                request_id=request_id,
                attempt_id=attempt_id,
                step_name=StepName.RESOURCE_SHARING.value,
                status=StepStatus.FAILED.value,
                correlation_id=correlation_id,
                started_at=started_at,
                completed_at=completed_at,
                error_code=error_code,
                message=error_msg,
                payload=payload,
            )
            await self._repository.save_meta(
                request_id=request_id,
                attempt_id=attempt_id,
                status=StepStatus.FAILED.value,
                correlation_id=correlation_id,
                failed_step=StepName.RESOURCE_SHARING.value,
            )
            await self._failure_publisher.publish(
                {
                    "eventType": "WorkflowFailed",
                    "eventVersion": 1,
                    "requestId": request_id,
                    "attemptId": attempt_id,
                    "correlationId": correlation_id,
                    "terminalStatus": "FAILED",
                    "failedStep": StepName.RESOURCE_SHARING.value,
                    "errorCode": error_code,
                    "message": error_msg,
                    "occurredAt": completed_at,
                    "payload": payload,
                }
            )
            return ProcessStepResult(
                message_id=message.message_id,
                request_id=request_id,
                status=StepStatus.FAILED,
                error_code=error_code,
            )

        # Success path
        completed_at = datetime.now(UTC).isoformat()
        payload["share_arn"] = share_arn
        payload["resource_sharing_status"] = "SHARED"
        resource_ref = {
            "share_arn": share_arn,
            "database_name": message.database_name,
            "producer_account_id": message.producer_account_id,
        }

        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.RESOURCE_SHARING.value,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            started_at=started_at,
            completed_at=completed_at,
            payload=payload,
            resource_ref=resource_ref,
        )

        outbound_event = {
            "eventType": "ResourceShared",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "stepName": StepName.RESOURCE_SHARING.value,
            "status": StepStatus.SUCCEEDED.value,
            "occurredAt": completed_at,
            "payload": payload,
        }
        await self._next_publisher.publish(outbound_event)

        logger.info("Resource sharing SUCCEEDED for requestId=%s share_arn=%s", request_id, share_arn)
        return ProcessStepResult(
            message_id=message.message_id,
            request_id=request_id,
            status=StepStatus.SUCCEEDED,
        )

    @staticmethod
    def _share_resource(message: IncomingMessage) -> str:
        if message.action == "fail" or message.fail_at_step == StepName.RESOURCE_SHARING.value:
            raise ResourceSharingError("Simulated resource sharing failure in Lake Formation/RAM.")

        if not message.producer_account_id or not message.database_name:
            raise ResourceSharingError("Missing required parameters for resource sharing.")

        return f"arn:aws:ram:us-east-1:{message.producer_account_id}:resource-share/{uuid.uuid4()}"
