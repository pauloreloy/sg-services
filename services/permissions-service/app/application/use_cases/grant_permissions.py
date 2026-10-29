"""Use case: grant Lake Formation permissions and complete choreographic workflow."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto import ProcessStepResult
from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import InvalidMessagePayloadError, PermissionGrantError
from app.domain.models import IncomingMessage
from app.domain.ports import QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class GrantPermissionsUseCase:
    """Grants final Lake Formation permissions, updates global META status, and publishes terminal event."""

    def __init__(
        self,
        repository: StepRepositoryPort,
        completed_publisher: QueuePublisherPort,
        failure_publisher: QueuePublisherPort,
    ) -> None:
        self._repository = repository
        self._completed_publisher = completed_publisher
        self._failure_publisher = failure_publisher

    async def execute(self, message: IncomingMessage) -> ProcessStepResult:
        request_id = message.request_id
        attempt_id = message.attempt_id
        correlation_id = message.correlation_id
        payload = message.inner_payload

        # 1. Idempotency check
        existing = await self._repository.find_step(
            request_id=request_id,
            step_name=StepName.PERMISSIONS.value,
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
            step_name=StepName.PERMISSIONS.value,
            status=StepStatus.RUNNING.value,
            correlation_id=correlation_id,
            started_at=started_at,
            payload=payload,
        )

        try:
            self._grant_permissions(message)
        except (PermissionGrantError, InvalidMessagePayloadError) as exc:
            completed_at = datetime.now(UTC).isoformat()
            error_code = "PERMISSION_GRANT_ERROR"
            error_msg = str(exc)

            await self._repository.save_step(
                request_id=request_id,
                attempt_id=attempt_id,
                step_name=StepName.PERMISSIONS.value,
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
                failed_step=StepName.PERMISSIONS.value,
            )
            await self._failure_publisher.publish(
                {
                    "eventType": "WorkflowFailed",
                    "eventVersion": 1,
                    "requestId": request_id,
                    "attemptId": attempt_id,
                    "correlationId": correlation_id,
                    "terminalStatus": "FAILED",
                    "failedStep": StepName.PERMISSIONS.value,
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
        payload["permissions_status"] = "GRANTED"
        resource_ref = {
            "iam_principal_arn": message.iam_principal_arn,
            "permissions": message.permissions,
        }

        # 1. Save step status
        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.PERMISSIONS.value,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            started_at=started_at,
            completed_at=completed_at,
            payload=payload,
            resource_ref=resource_ref,
        )

        # 2. Update global META status to SUCCEEDED
        await self._repository.save_meta(
            request_id=request_id,
            attempt_id=attempt_id,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            payload=payload,
        )

        # 3. Publish terminal event to workflow-completed
        terminal_event = {
            "eventType": "WorkflowCompleted",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "terminalStatus": "SUCCEEDED",
            "occurredAt": completed_at,
            "payload": payload,
        }
        await self._completed_publisher.publish(terminal_event)

        logger.info("Governance workflow SUCCEEDED for requestId=%s", request_id)
        return ProcessStepResult(
            message_id=message.message_id,
            request_id=request_id,
            status=StepStatus.SUCCEEDED,
        )

    @staticmethod
    def _grant_permissions(message: IncomingMessage) -> None:
        if message.action == "fail" or message.fail_at_step == StepName.PERMISSIONS.value:
            raise PermissionGrantError("Simulated permission grant failure in Lake Formation.")

        if not message.iam_principal_arn and not message.inner_payload.get("iam_principal_arn"):
            raise PermissionGrantError("Missing iam_principal_arn to grant permissions.")
