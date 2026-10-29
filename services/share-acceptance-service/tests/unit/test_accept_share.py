"""Unit tests for AcceptShareUseCase."""

import pytest

from app.application.use_cases.accept_share import AcceptShareUseCase
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
async def test_accept_share_success():
    repo = DummyStepRepository()
    next_pub = DummyPublisher()
    fail_pub = DummyPublisher()

    use_case = AcceptShareUseCase(repo, next_pub, fail_pub)
    msg = IncomingMessage(
        message_id="msg-1",
        receipt_handle="rh-1",
        payload={
            "requestId": "req-1",
            "attemptId": "attempt-0001",
            "correlationId": "corr-1",
            "consumer_account_id": "444455556666",
            "share_arn": "arn:aws:ram:us-east-1:111122223333:resource-share/123",
            "action": "success",
        },
    )

    result = await use_case.execute(msg)
    assert result.status == StepStatus.SUCCEEDED
    assert len(next_pub.published) == 1
    assert next_pub.published[0]["eventType"] == "ShareAccepted"
    assert len(fail_pub.published) == 0


@pytest.mark.asyncio
async def test_accept_share_failure():
    repo = DummyStepRepository()
    next_pub = DummyPublisher()
    fail_pub = DummyPublisher()

    use_case = AcceptShareUseCase(repo, next_pub, fail_pub)
    msg = IncomingMessage(
        message_id="msg-2",
        receipt_handle="rh-2",
        payload={
            "requestId": "req-2",
            "attemptId": "attempt-0001",
            "correlationId": "corr-2",
            "consumer_account_id": "444455556666",
            "share_arn": "arn:aws:ram:us-east-1:111122223333:resource-share/123",
            "action": "fail",
        },
    )

    result = await use_case.execute(msg)
    assert result.status == StepStatus.FAILED
    assert result.error_code == "SHARE_ACCEPTANCE_ERROR"
    assert len(next_pub.published) == 0
    assert len(fail_pub.published) == 1
    assert fail_pub.published[0]["eventType"] == "WorkflowFailed"
