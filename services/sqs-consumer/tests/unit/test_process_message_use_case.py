"""Unit tests for ``ProcessMessageUseCase`` using in-memory fake adapters.

These tests exercise the business rule in complete isolation from AWS, which
is the whole point of hexagonal architecture: the application/domain layers
can be tested without any infrastructure dependency.
"""

from __future__ import annotations

import pytest

from app.application.use_cases import ProcessMessageUseCase
from app.domain.enums import ProcessingStatus
from app.domain.models import IncomingMessage, ProcessingRecord
from app.domain.ports import (
    ProcessingRecordRepositoryPort,
    QueuePublisherPort,
)


class FakeRepository(ProcessingRecordRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[ProcessingRecord] = []

    async def save(self, record: ProcessingRecord) -> None:
        self.saved.append(record)


class FakePublisher(QueuePublisherPort):
    def __init__(self) -> None:
        self.published: list[dict] = []

    async def publish(self, message: dict) -> None:
        self.published.append(dict(message))


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def success_publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def failure_publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def use_case(repository, success_publisher, failure_publisher) -> ProcessMessageUseCase:
    return ProcessMessageUseCase(
        repository=repository,
        success_publisher=success_publisher,
        failure_publisher=failure_publisher,
    )


@pytest.mark.asyncio
async def test_action_success_is_persisted_and_published_to_success_queue(
    use_case, repository, success_publisher, failure_publisher
):
    message = IncomingMessage(
        message_id="msg-1",
        receipt_handle="rh-1",
        payload={"action": "success", "foo": "bar"},
    )

    result = await use_case.execute(message)

    assert result.status is ProcessingStatus.SUCCESS
    assert len(repository.saved) == 1
    assert repository.saved[0].status is ProcessingStatus.SUCCESS
    assert len(success_publisher.published) == 1
    assert success_publisher.published[0]["status"] == "SUCCESS"
    assert failure_publisher.published == []


@pytest.mark.asyncio
async def test_action_fail_is_persisted_and_published_to_failure_queue(
    use_case, repository, success_publisher, failure_publisher
):
    message = IncomingMessage(
        message_id="msg-2",
        receipt_handle="rh-2",
        payload={"action": "fail"},
    )

    result = await use_case.execute(message)

    assert result.status is ProcessingStatus.FAILURE
    assert len(repository.saved) == 1
    assert repository.saved[0].status is ProcessingStatus.FAILURE
    assert repository.saved[0].reason is not None
    assert len(failure_publisher.published) == 1
    assert failure_publisher.published[0]["status"] == "FAILURE"
    assert success_publisher.published == []


@pytest.mark.asyncio
async def test_action_is_case_insensitive(use_case, success_publisher, failure_publisher):
    message = IncomingMessage(
        message_id="msg-3", receipt_handle="rh-3", payload={"action": "FAIL"}
    )

    result = await use_case.execute(message)

    assert result.status is ProcessingStatus.FAILURE
    assert len(failure_publisher.published) == 1


@pytest.mark.asyncio
async def test_missing_action_key_is_treated_as_failure(
    use_case, repository, failure_publisher
):
    message = IncomingMessage(message_id="msg-4", receipt_handle="rh-4", payload={"foo": "bar"})

    result = await use_case.execute(message)

    assert result.status is ProcessingStatus.FAILURE
    assert "action" in repository.saved[0].reason
    assert len(failure_publisher.published) == 1


@pytest.mark.asyncio
async def test_any_action_other_than_fail_is_success(use_case, success_publisher):
    message = IncomingMessage(
        message_id="msg-5", receipt_handle="rh-5", payload={"action": "approve"}
    )

    result = await use_case.execute(message)

    assert result.status is ProcessingStatus.SUCCESS
    assert len(success_publisher.published) == 1
