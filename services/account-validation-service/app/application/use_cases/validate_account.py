"""Use case: validate account eligibility and cross-account topology."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto import ProcessStepResult
from app.domain.enums import StepName, StepStatus
from app.domain.exceptions import AccountNotEligibleError, InvalidMessagePayloadError
from app.domain.models import IncomingMessage
from app.domain.ports import QueuePublisherPort, StepRepositoryPort

logger = logging.getLogger(__name__)


class ValidateAccountUseCase:
    """Validates producer and consumer accounts, then forwards to catalog validation."""

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

        logger.info(
            "Validating account for requestId=%s attemptId=%s correlationId=%s",
            request_id,
            attempt_id,
            correlation_id,
            extra={
                "requestId": request_id,
                "attemptId": attempt_id,
                "correlationId": correlation_id,
                "stepName": StepName.ACCOUNT_VALIDATION.value,
            },
        )

        # 1. Idempotency check: if already SUCCEEDED for this attempt, avoid duplicate effects
        existing = await self._repository.find_step(
            request_id=request_id,
            step_name=StepName.ACCOUNT_VALIDATION.value,
            attempt_id=attempt_id,
        )
        if existing and existing.get("status") == StepStatus.SUCCEEDED.value:
            logger.info("Step %s already SUCCEEDED for attempt %s, skipping.", StepName.ACCOUNT_VALIDATION.value, attempt_id)
            return ProcessStepResult(
                message_id=message.message_id,
                request_id=request_id,
                status=StepStatus.SUCCEEDED,
            )

        started_at = datetime.now(UTC).isoformat()
        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.ACCOUNT_VALIDATION.value,
            status=StepStatus.RUNNING.value,
            correlation_id=correlation_id,
            started_at=started_at,
            payload=payload,
        )

        try:
            self._validate_accounts(message)
        except (AccountNotEligibleError, InvalidMessagePayloadError) as exc:
            completed_at = datetime.now(UTC).isoformat()
            error_code = "ACCOUNT_NOT_ELIGIBLE"
            error_msg = str(exc)

            logger.warning(
                "Account validation failed for requestId=%s: %s",
                request_id,
                error_msg,
                extra={"errorCode": error_code, "stepName": StepName.ACCOUNT_VALIDATION.value},
            )

            await self._repository.save_step(
                request_id=request_id,
                attempt_id=attempt_id,
                step_name=StepName.ACCOUNT_VALIDATION.value,
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
                failed_step=StepName.ACCOUNT_VALIDATION.value,
            )
            await self._failure_publisher.publish(
                {
                    "eventType": "WorkflowFailed",
                    "eventVersion": 1,
                    "requestId": request_id,
                    "attemptId": attempt_id,
                    "correlationId": correlation_id,
                    "terminalStatus": "FAILED",
                    "failedStep": StepName.ACCOUNT_VALIDATION.value,
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
        payload["account_validation_status"] = "ELIGIBLE"
        resource_ref = {
            "producer_account_id": message.producer_account_id,
            "consumer_account_id": message.consumer_account_id,
        }

        await self._repository.save_step(
            request_id=request_id,
            attempt_id=attempt_id,
            step_name=StepName.ACCOUNT_VALIDATION.value,
            status=StepStatus.SUCCEEDED.value,
            correlation_id=correlation_id,
            started_at=started_at,
            completed_at=completed_at,
            payload=payload,
            resource_ref=resource_ref,
        )

        outbound_event = {
            "eventType": "AccountValidated",
            "eventVersion": 1,
            "requestId": request_id,
            "attemptId": attempt_id,
            "correlationId": correlation_id,
            "stepName": StepName.ACCOUNT_VALIDATION.value,
            "status": StepStatus.SUCCEEDED.value,
            "occurredAt": completed_at,
            "payload": payload,
        }
        await self._next_publisher.publish(outbound_event)

        logger.info("Account validation SUCCEEDED for requestId=%s", request_id)
        return ProcessStepResult(
            message_id=message.message_id,
            request_id=request_id,
            status=StepStatus.SUCCEEDED,
        )

    @staticmethod
    def _validate_accounts(message: IncomingMessage) -> None:
        if message.action == "fail" or message.fail_at_step == StepName.ACCOUNT_VALIDATION.value:
            raise AccountNotEligibleError(
                f"Account validation simulated failure for consumer account '{message.consumer_account_id}'."
            )

        if not message.producer_account_id:
            raise AccountNotEligibleError("Missing producer_account_id in governance request.")
        if not message.consumer_account_id:
            raise AccountNotEligibleError("Missing consumer_account_id in governance request.")
