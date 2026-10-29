"""Use case: execute diagnostic reconstruction of the governance workflow."""

from __future__ import annotations

import hashlib
import logging

from app.domain.models import DiagnosticOutcome, TerminalEventMessage
from app.domain.ports import (
    CheckStepClientPort,
    NotificationPublisherPort,
    StepFunctionsInvokerPort,
)

logger = logging.getLogger(__name__)

STEP_ORDER = [
    "ACCOUNT_VALIDATION",
    "CATALOG_VALIDATION",
    "RESOURCE_SHARING",
    "SHARE_ACCEPTANCE",
    "RESOURCE_LINKS",
    "PERMISSIONS",
]


class RunDiagnosticUseCase:
    """Invokes Step Functions Express and checks steps sequentially according to ADR Section 6."""

    def __init__(
        self,
        sfn_invoker: StepFunctionsInvokerPort,
        check_step_client: CheckStepClientPort,
        notifier: NotificationPublisherPort,
        state_machine_name: str = "GovernanceDiagnosticWorkflow",
        sns_topic_name: str = "sg-governance-notifications",
    ) -> None:
        self._sfn_invoker = sfn_invoker
        self._check_step_client = check_step_client
        self._notifier = notifier
        self._state_machine_name = state_machine_name
        self._sns_topic_name = sns_topic_name

    async def execute(self, event: TerminalEventMessage) -> DiagnosticOutcome:
        request_id = event.request_id
        attempt_id = event.attempt_id
        terminal_status = event.terminal_status

        logger.info(
            "Starting visual diagnostic for requestId=%s attemptId=%s terminalStatus=%s",
            request_id,
            attempt_id,
            terminal_status,
        )

        # 1. Deterministic execution name for Step Functions (ADR 5.7)
        raw_name = f"{request_id}_{attempt_id}_{terminal_status}"
        exec_hash = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:32]
        execution_name = f"diag-{exec_hash}"

        input_payload = {
            "requestId": request_id,
            "attemptId": attempt_id,
            "terminalStatus": terminal_status,
        }

        execution_arn = await self._sfn_invoker.start_execution(
            state_machine_name=self._state_machine_name,
            execution_name=execution_name,
            input_payload=input_payload,
        )

        # 2. Sequential checkStep evaluation
        evaluated: list[dict[str, Any]] = []
        first_failed: str | None = None

        for step in STEP_ORDER:
            try:
                res = await self._check_step_client.check_step(
                    request_id=request_id,
                    attempt_id=attempt_id,
                    step_name=step,
                )
                evaluated.append(res)
                if res.get("status") == "FAILED":
                    first_failed = step
                    logger.info("Found first FAILED step: %s", step)
                    break
            except Exception as exc:
                logger.warning("Diagnostic checkStep exception for %s: %s", step, exc)
                evaluated.append({"stepName": step, "status": "UNKNOWN", "error": str(exc)})
                break

        # 3. Publish SNS notification (ADR 4.1 Step 8)
        notification_payload = {
            "requestId": request_id,
            "attemptId": attempt_id,
            "terminalStatus": terminal_status,
            "firstFailedStep": first_failed,
            "stepsEvaluated": evaluated,
            "executionArn": execution_arn,
        }
        await self._notifier.publish_notification(
            topic_name=self._sns_topic_name,
            message=notification_payload,
        )

        return DiagnosticOutcome(
            request_id=request_id,
            attempt_id=attempt_id,
            terminal_status=terminal_status,
            steps_evaluated=evaluated,
            first_failed_step=first_failed,
            step_functions_execution_arn=execution_arn,
            sns_published=True,
        )
