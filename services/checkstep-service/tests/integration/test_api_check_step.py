"""HTTP-level tests for POST /checkStep using FastAPI's TestClient.

The real DynamoDB-backed use case dependency is overridden with a fake, since
this test's purpose is to validate the HTTP contract (status codes, request/
response schemas), not the AWS integration (covered separately).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.application.dto import CheckStepResult
from app.domain.enums import ProcessingStatus
from app.domain.exceptions import GrantNotFoundError
from app.infrastructure.api.dependencies import get_grant_status_use_case
from main import create_app


class FakeUseCase:
    def __init__(self, result: CheckStepResult | None = None) -> None:
        self._result = result

    async def execute(self, grant_id: str) -> CheckStepResult:
        if self._result is None:
            raise GrantNotFoundError(grant_id)
        return self._result


@pytest.fixture
def app():
    return create_app()


def test_check_step_returns_200_when_found(app):
    result = CheckStepResult(
        grant_id="grant-1",
        status=ProcessingStatus.SUCCESS,
        action="success",
        reason=None,
        record_id="record-1",
        message_id="msg-1",
        processed_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_grant_status_use_case] = lambda: FakeUseCase(result)

    with TestClient(app) as client:
        response = client.post("/checkStep", json={"grant_id": "grant-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["grant_id"] == "grant-1"
    assert body["status"] == "SUCCESS"


def test_check_step_returns_404_when_not_found(app):
    app.dependency_overrides[get_grant_status_use_case] = lambda: FakeUseCase(None)

    with TestClient(app) as client:
        response = client.post("/checkStep", json={"grant_id": "unknown"})

    assert response.status_code == 404


def test_check_step_returns_422_when_grant_id_missing(app):
    app.dependency_overrides[get_grant_status_use_case] = lambda: FakeUseCase(None)

    with TestClient(app) as client:
        response = client.post("/checkStep", json={})

    assert response.status_code == 422


def test_health_endpoint(app):
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
