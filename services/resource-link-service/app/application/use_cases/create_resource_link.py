"""Use case: create resource links in consumer Glue Data Catalog."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto import ProcessStepResult
from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import InvalidMessagePayloadError, ResourceLinkCreationError
from app.domain.models import IncomingMessage
from app.domain.ports import QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class CreateResourceLinkUseCase:
    """Creates Resource Links in the consumer Glue Data Catalog, then forwards to permissions service."""

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
            step_name=StepName.RESOURCE_LINKS.value,
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
            step_name=StepName.RESOURCE_LINKS.value,
            status=StepStatus.RUNNING.value,
            correlation_id=correlation_id,
            started_at=started_at,
            payload=payload,
        )

        try:
            resource_link_name = self._create_resource_link(message)
        except (ResourceLinkCreationError, InvalidMessagePayloadError) as exc:
            completed_at = datetime.now(UTC).isoformat()
            error_code = "RESOURCE_LINK_CREATION_ERROR"
            error_msg = str(exc)

            await self._repository.save_step(
                request_id=request_id,
                attempt_id=attempt_id,
                step_name=StepName.RESOURCE_LINKS.value,
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
                failed_step=StepName.RESOURCE_LINKS.value,
            )
            await self._failure_publisher.publish(
                {
                    "eventType": "WorkflowFailed",
                    "eventVersion": 1,
                    "requestId": request_id,
                    "attemptId": attempt_id,
                    "correlationId": correlation_id,
                    "terminalStatus": "FAILED",
                    "failedStep": StepName.RESOURCE_LINKS.value,
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
        payload["resource_link_name"] = resource_link_name
        payload["resource_links_status"] = "CREATED"
        resource_ref = {
            "resource_link_name": resource_link_name,
            "consumer_account_id": message.consumer_account_id,
            "database_name": message.database_name,
        }

        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.RESOURCE_LINKS.value,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            started_at=started_at,
            completed_at=completed_at,
            payload=payload,
            resource_ref=resource_ref,
        )

        outbound_event = {
            "eventType": "ResourceLinkCreated",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "stepName": StepName.RESOURCE_LINKS.value,
            "status": StepStatus.SUCCEEDED.value,
            "occurredAt": completed_at,
            "payload": payload,
        }
        await self._next_publisher.publish(outbound_event)

        logger.info("Resource link creation SUCCEEDED for requestId=%s name=%s", request_id, resource_link_name)
        return ProcessStepResult(
            message_id=message.message_id,
            request_id=request_id,
            status=StepStatus.SUCCEEDED,
        )

    @staticmethod
    def _create_resource_link(message: IncomingMessage) -> str:
        if message.action == "fail" or message.fail_at_step == StepName.RESOURCE_LINKS.value:
            raise ResourceLinkCreationError("Simulated resource link creation error in Glue Data Catalog.")

        table = message.table_names[0] if message.table_names else "default_tbl"
        return f"rl_{message.database_name}_{table}"
