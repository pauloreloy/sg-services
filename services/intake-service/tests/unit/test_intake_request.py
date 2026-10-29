"""Unit tests for IntakeRequestUseCase."""

import pytest

from app.application.use_cases.intake_request import IntakeRequestUseCase
from app.domain.models import GovernanceRequest


class DummyRepo:
    def __init__(self):
        self.meta = {}

    async def save_meta(self, **kwargs):
        self.meta = kwargs


class DummyPublisher:
    def __init__(self):
        self.published = []

    async def publish(self, message):
        self.published.append(message)


class DummyStorage:
    def __init__(self, data):
        self.data = data

    async def get_payload(self, bucket: str, key: str):
        return self.data


@pytest.mark.asyncio
async def test_intake_request_direct():
    repo = DummyRepo()
    publisher = DummyPublisher()
    use_case = IntakeRequestUseCase(repo, publisher)

    req = GovernanceRequest(
        producer_account_id="111122223333",
        consumer_account_id="444455556666",
        database_name="sales_db",
        table_names=["orders"],
        iam_principal_arn="arn:aws:iam::444455556666:role/Analyst",
    )

    res = await use_case.execute(req)
    assert res.status == "ACCEPTED"
    assert repo.meta["status"] == "RUNNING"
    assert len(publisher.published) == 1
    assert publisher.published[0]["stepName"] == "ACCOUNT_VALIDATION"


@pytest.mark.asyncio
async def test_intake_request_with_s3_storage():
    repo = DummyRepo()
    publisher = DummyPublisher()
    storage = DummyStorage({"database_name": "remote_db", "table_names": ["remote_table"]})
    use_case = IntakeRequestUseCase(repo, publisher, storage)

    req = GovernanceRequest(
        producer_account_id="111122223333",
        consumer_account_id="444455556666",
        database_name="",
        table_names=[],
        iam_principal_arn="arn:aws:iam::444455556666:role/Analyst",
        s3_bucket="sg-governance-payloads",
        s3_key="payloads/req-1.json",
    )

    res = await use_case.execute(req)
    assert res.status == "ACCEPTED"
    assert publisher.published[0]["payload"]["database_name"] == "remote_db"
