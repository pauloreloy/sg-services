"""Unit tests for GetStepStatusUseCase."""

import pytest

from app.application.use_cases import GetStepStatusUseCase
from app.domain.exceptions import StepNotFoundError
from app.domain.models import StepStatusRecord


class DummyStepRepository:
    def __init__(self, record: StepStatusRecord | None = None):
        self.record = record

    async def find_step_status(self, request_id: str, step_name: str, attempt_id: str | None = None):
        if self.record and self.record.request_id == request_id and self.record.step_name == step_name:
            return self.record
        return None


@pytest.mark.asyncio
async def test_get_step_status_success():
    record = StepStatusRecord(
        request_id="req-100",
        attempt_id="attempt-0001",
        step_name="ACCOUNT_VALIDATION",
        status="SUCCEEDED",
        started_at="2026-10-29T00:00:00Z",
        completed_at="2026-10-29T00:00:05Z",
    )
    repo = DummyStepRepository(record)
    use_case = GetStepStatusUseCase(repo)

    result = await use_case.execute(request_id="req-100", step_name="ACCOUNT_VALIDATION")
    assert result.status == "SUCCEEDED"
    assert result.request_id == "req-100"


@pytest.mark.asyncio
async def test_get_step_status_not_found():
    repo = DummyStepRepository(None)
    use_case = GetStepStatusUseCase(repo)

    with pytest.raises(StepNotFoundError):
        await use_case.execute(request_id="unknown", step_name="ACCOUNT_VALIDATION")
