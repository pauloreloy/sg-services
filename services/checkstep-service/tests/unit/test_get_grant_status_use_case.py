"""Unit tests for ``GetGrantStatusUseCase`` using an in-memory fake repository."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases import GetGrantStatusUseCase
from app.domain.enums import ProcessingStatus
from app.domain.exceptions import GrantNotFoundError
from app.domain.models import GrantStatus
from app.domain.ports import GrantStatusRepositoryPort


class FakeRepository(GrantStatusRepositoryPort):
    def __init__(self, records: dict[str, GrantStatus] | None = None) -> None:
        self._records = records or {}

    async def find_latest_by_grant_id(self, grant_id: str) -> GrantStatus | None:
        return self._records.get(grant_id)


def _grant_status(grant_id: str, status: ProcessingStatus) -> GrantStatus:
    return GrantStatus(
        grant_id=grant_id,
        record_id="record-1",
        message_id="msg-1",
        action="success" if status is ProcessingStatus.SUCCESS else "fail",
        status=status,
        processed_at=datetime.now(UTC),
        reason=None if status is ProcessingStatus.SUCCESS else "explicit fail",
    )


@pytest.mark.asyncio
async def test_execute_returns_result_when_grant_found():
    grant_status = _grant_status("grant-1", ProcessingStatus.SUCCESS)
    repository = FakeRepository({"grant-1": grant_status})
    use_case = GetGrantStatusUseCase(repository=repository)

    result = await use_case.execute("grant-1")

    assert result.grant_id == "grant-1"
    assert result.status is ProcessingStatus.SUCCESS
    assert result.record_id == "record-1"


@pytest.mark.asyncio
async def test_execute_raises_grant_not_found_when_missing():
    repository = FakeRepository({})
    use_case = GetGrantStatusUseCase(repository=repository)

    with pytest.raises(GrantNotFoundError):
        await use_case.execute("unknown-grant")
