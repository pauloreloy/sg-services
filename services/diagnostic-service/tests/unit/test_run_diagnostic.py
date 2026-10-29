"""Unit tests for RunDiagnosticUseCase."""

import pytest

from app.application.use_cases.run_diagnostic import RunDiagnosticUseCase
from app.domain.models import TerminalEventMessage


class DummySfnInvoker:
    def __init__(self):
        self.invoked = []

    async def start_execution(self, state_machine_name, execution_name, input_payload):
        self.invoked.append((state_machine_name, execution_name, input_payload))
        return f"arn:aws:states:us-east-1:123456789012:execution:{state_machine_name}:{execution_name}"


class DummyCheckStepClient:
    def __init__(self, step_results=None):
        self.step_results = step_results or {}

    async def check_step(self, request_id, attempt_id, step_name):
        return self.step_results.get(
            step_name, {"stepName": step_name, "status": "SUCCEEDED"}
        )


class DummyNotifier:
    def __init__(self):
        self.notifications = []

    async def publish_notification(self, topic_name, message):
        self.notifications.append((topic_name, message))


@pytest.mark.asyncio
async def test_run_diagnostic_all_succeeded():
    sfn = DummySfnInvoker()
    check = DummyCheckStepClient()
    notifier = DummyNotifier()

    use_case = RunDiagnosticUseCase(sfn, check, notifier)
    event = TerminalEventMessage(
        message_id="msg-term-1",
        receipt_handle="rh-term-1",
        payload={
            "requestId": "req-ok",
            "attemptId": "attempt-0001",
            "terminalStatus": "SUCCEEDED",
        },
    )

    outcome = await use_case.execute(event)
    assert outcome.terminal_status == "SUCCEEDED"
    assert outcome.first_failed_step is None
    assert len(outcome.steps_evaluated) == 6
    assert len(sfn.invoked) == 1
    assert len(notifier.notifications) == 1


@pytest.mark.asyncio
async def test_run_diagnostic_finds_first_failed_step():
    sfn = DummySfnInvoker()
    # Step 3 (RESOURCE_SHARING) failed
    check = DummyCheckStepClient(
        {
            "ACCOUNT_VALIDATION": {"stepName": "ACCOUNT_VALIDATION", "status": "SUCCEEDED"},
            "CATALOG_VALIDATION": {"stepName": "CATALOG_VALIDATION", "status": "SUCCEEDED"},
            "RESOURCE_SHARING": {"stepName": "RESOURCE_SHARING", "status": "FAILED", "errorCode": "ERR"},
        }
    )
    notifier = DummyNotifier()

    use_case = RunDiagnosticUseCase(sfn, check, notifier)
    event = TerminalEventMessage(
        message_id="msg-term-2",
        receipt_handle="rh-term-2",
        payload={
            "requestId": "req-fail",
            "attemptId": "attempt-0001",
            "terminalStatus": "FAILED",
            "failedStep": "RESOURCE_SHARING",
        },
    )

    outcome = await use_case.execute(event)
    assert outcome.terminal_status == "FAILED"
    assert outcome.first_failed_step == "RESOURCE_SHARING"
    assert len(outcome.steps_evaluated) == 3  # Stopped right at first failure!
    assert len(sfn.invoked) == 1
    assert len(notifier.notifications) == 1
