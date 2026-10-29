"""Unit tests for GrantPermissionsUseCase."""

import pytest

from app.application.use_cases.grant_permissions import GrantPermissionsUseCase
from app.domain.enums import StepStatus
from app.domain.models import IncomingMessage


class DummyStepRepository:
    def __init__(self):
        self.steps = {}
        self.meta = {}

    async def save_step(self, **kwargs):
        self.steps[kwargs["step_name"]] = kwargs

    async def find_step(self, request_id, step_name, attempt_id):
        return self.steps.get(step_name)

    async def save_meta(self, **kwargs):
        self.meta = kwargs


class DummyPublisher:
    def __init__(self):
        self.published = []

    async def publish(self, message):
        self.published.append(message)


@pytest.mark.asyncio
async def test_grant_permissions_success():
    repo = DummyStepRepository()
    comp_pub = DummyPublisher()
    fail_pub = DummyPublisher()

    use_case = GrantPermissionsUseCase(repo, comp_pub, fail_pub)
    msg = IncomingMessage(
        message_id="msg-1",
        receipt_handle="rh-1",
        payload={
            "requestId": "req-1",
            "attemptId": "attempt-0001",
            "correlationId": "corr-1",
            "iam_principal_arn": "arn:aws:iam::444455556666:role/DataAnalyst",
            "permissions": ["DESCRIBE", "SELECT"],
            "action": "success",
        },
    )

    result = await use_case.execute(msg)
    assert result.status == StepStatus.SUCCEEDED
    assert len(comp_pub.published) == 1
    assert comp_pub.published[0]["eventType"] == "WorkflowCompleted"
    assert comp_pub.published[0]["terminalStatus"] == "SUCCEEDED"
    assert repo.meta["status"] == "SUCCEEDED"
    assert len(fail_pub.published) == 0


@pytest.mark.asyncio
async def test_grant_permissions_failure():
    repo = DummyStepRepository()
    comp_pub = DummyPublisher()
    fail_pub = DummyPublisher()

    use_case = GrantPermissionsUseCase(repo, comp_pub, fail_pub)
    msg = IncomingMessage(
        message_id="msg-2",
        receipt_handle="rh-2",
        payload={
            "requestId": "req-2",
            "attemptId": "attempt-0001",
            "correlationId": "corr-2",
            "iam_principal_arn": "arn:aws:iam::444455556666:role/DataAnalyst",
            "action": "fail",
        },
    )

    result = await use_case.execute(msg)
    assert result.status == StepStatus.FAILED
    assert result.error_code == "PERMISSION_GRANT_ERROR"
    assert len(comp_pub.published) == 0
    assert len(fail_pub.published) == 1
    assert fail_pub.published[0]["eventType"] == "WorkflowFailed"
    assert repo.meta["status"] == "FAILED"
