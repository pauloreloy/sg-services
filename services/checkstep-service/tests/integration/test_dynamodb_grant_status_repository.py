"""Integration tests for the DynamoDB adapter, using moto to mock AWS locally.

Validates that querying the `grant_id-processed_at-index` GSI correctly
returns the most recent record for a given grant_id, without needing a table
scan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from app.domain.enums import ProcessingStatus
from app.infrastructure.adapters import DynamoDbGrantStatusRepository

AWS_REGION = "us-east-1"
TABLE_NAME = "sg-share-processing-records"
INDEX_NAME = "grant_id-processed_at-index"


@pytest.fixture
def aws_mock():
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_table(aws_mock):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "record_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "record_id", "AttributeType": "S"},
            {"AttributeName": "grant_id", "AttributeType": "S"},
            {"AttributeName": "processed_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": INDEX_NAME,
                "KeySchema": [
                    {"AttributeName": "grant_id", "KeyType": "HASH"},
                    {"AttributeName": "processed_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.mark.asyncio
async def test_find_latest_by_grant_id_returns_none_when_absent(dynamodb_table):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    repository = DynamoDbGrantStatusRepository(
        dynamodb_resource=dynamodb, table_name=TABLE_NAME, index_name=INDEX_NAME
    )

    result = await repository.find_latest_by_grant_id("missing-grant")

    assert result is None


@pytest.mark.asyncio
async def test_find_latest_by_grant_id_returns_most_recent_record(dynamodb_table):
    older = datetime.now(UTC) - timedelta(minutes=5)
    newer = datetime.now(UTC)

    dynamodb_table.put_item(
        Item={
            "record_id": "record-older",
            "grant_id": "grant-1",
            "message_id": "msg-older",
            "action": "fail",
            "status": ProcessingStatus.FAILURE.value,
            "reason": "first attempt failed",
            "payload": "{}",
            "processed_at": older.isoformat(),
        }
    )
    dynamodb_table.put_item(
        Item={
            "record_id": "record-newer",
            "grant_id": "grant-1",
            "message_id": "msg-newer",
            "action": "success",
            "status": ProcessingStatus.SUCCESS.value,
            "reason": None,
            "payload": "{}",
            "processed_at": newer.isoformat(),
        }
    )

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    repository = DynamoDbGrantStatusRepository(
        dynamodb_resource=dynamodb, table_name=TABLE_NAME, index_name=INDEX_NAME
    )

    result = await repository.find_latest_by_grant_id("grant-1")

    assert result is not None
    assert result.record_id == "record-newer"
    assert result.status is ProcessingStatus.SUCCESS
