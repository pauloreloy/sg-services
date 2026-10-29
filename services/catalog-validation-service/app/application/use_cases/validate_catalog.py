"""Use case: validate database, tables and ownership in Glue/Lake Formation catalog."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto import ProcessStepResult
from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import CatalogValidationError, InvalidMessagePayloadError
from app.domain.models import IncomingMessage
from app.domain.ports import QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class ValidateCatalogUseCase:
    """Validates catalog entities, then forwards to resource sharing."""

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
            step_name=StepName.CATALOG_VALIDATION.value,
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
            step_name=StepName.CATALOG_VALIDATION.value,
            status=StepStatus.RUNNING.value,
            correlation_id=correlation_id,
            started_at=started_at,
            payload=payload,
        )

        try:
            self._validate_catalog(message)
        except (CatalogValidationError, InvalidMessagePayloadError) as exc:
            completed_at = datetime.now(UTC).isoformat()
            error_code = "CATALOG_VALIDATION_ERROR"
            error_msg = str(exc)

            await self._repository.save_step(
                request_id=request_id,
                attempt_id=attempt_id,
                step_name=StepName.CATALOG_VALIDATION.value,
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
                failed_step=StepName.CATALOG_VALIDATION.value,
            )
            await self._failure_publisher.publish(
                {
                    "eventType": "WorkflowFailed",
                    "eventVersion": 1,
                    "requestId": request_id,
                    "attemptId": attempt_id,
                    "correlationId": correlation_id,
                    "terminalStatus": "FAILED",
                    "failedStep": StepName.CATALOG_VALIDATION.value,
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
        payload["catalog_id"] = payload.get("catalog_id") or "central-catalog"
        payload["catalog_validation_status"] = "VALIDATED"
        resource_ref = {
            "database_name": message.database_name,
            "table_names": message.table_names,
            "catalog_id": payload["catalog_id"],
        }

        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.CATALOG_VALIDATION.value,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            started_at=started_at,
            completed_at=completed_at,
            payload=payload,
            resource_ref=resource_ref,
        )

        outbound_event = {
            "eventType": "CatalogValidated",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "stepName": StepName.CATALOG_VALIDATION.value,
            "status": StepStatus.SUCCEEDED.value,
            "occurredAt": completed_at,
            "payload": payload,
        }
        await self._next_publisher.publish(outbound_event)

        logger.info("Catalog validation SUCCEEDED for requestId=%s", request_id)
        return ProcessStepResult(
            message_id=message.message_id,
            request_id=request_id,
            status=StepStatus.SUCCEEDED,
        )

    @staticmethod
    def _validate_catalog(message: IncomingMessage) -> None:
        if message.action == "fail" or message.fail_at_step == StepName.CATALOG_VALIDATION.value:
            raise CatalogValidationError(
                f"Catalog validation simulated failure for database '{message.database_name}'."
            )

        if not message.database_name:
            raise CatalogValidationError("Missing database_name in governance request.")
        if not message.table_names:
            raise CatalogValidationError("Missing table_names in governance request.")
