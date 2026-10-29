"""Integration tests for account validation adapters using moto."""

import json

import boto3
import pytest
from moto import mock_aws

from app.domain.models import IncomingMessage
from app.infrastructure.adapters import (
    DynamoDbStepRepositoryAdapter,
    SqsQueueConsumerAdapter,
    SqsQueuePublisherAdapter,
)
from app.infrastructure.config import Settings

AWS_REGION = "us-east-1"


@pytest.fixture
def aws_mock():
    with mock_aws():
        yield


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_region=AWS_REGION,
        aws_endpoint_url=None,
        sqs_source_queue_name="access-validation",
        sqs_next_queue_name="database-validation",
        sqs_failure_queue_name="workflow-failed",
        dynamodb_table_name="sg-share-governance",
    )


@pytest.mark.asyncio
async def test_dynamodb_step_repository(aws_mock, settings: Settings):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    dynamodb.create_table(
        TableName=settings.dynamodb_table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    repo = DynamoDbStepRepositoryAdapter(dynamodb, settings.dynamodb_table_name)
    await repo.save_step(
        request_id="req-123",
        attempt_id="attempt-0001",
        step_name="ACCOUNT_VALIDATION",
        status="SUCCEEDED",
        started_at="2026-10-29T00:00:00Z",
        completed_at="2026-10-29T00:00:02Z",
    )

    item = await repo.find_step("req-123", "ACCOUNT_VALIDATION", "attempt-0001")
    assert item is not None
    assert item["status"] == "SUCCEEDED"
    assert item["stepName"] == "ACCOUNT_VALIDATION"


@pytest.mark.asyncio
async def test_sqs_consumer_and_publisher(aws_mock, settings: Settings):
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    sqs.create_queue(QueueName=settings.sqs_source_queue_name)
    sqs.create_queue(QueueName=settings.sqs_next_queue_name)

    consumer = SqsQueueConsumerAdapter(sqs, settings, settings.sqs_source_queue_name)
    publisher = SqsQueuePublisherAdapter(sqs, settings.sqs_next_queue_name)

    q_url = sqs.get_queue_url(QueueName=settings.sqs_source_queue_name)["QueueUrl"]
    sqs.send_message(
        QueueUrl=q_url,
        MessageBody=json.dumps({"requestId": "req-1", "action": "success"}),
    )

    messages = await consumer.receive_messages()
    assert len(messages) == 1
    assert messages[0].request_id == "req-1"

    await consumer.acknowledge(messages[0])
    remaining = sqs.receive_message(QueueUrl=q_url).get("Messages", [])
    assert remaining == []

    await publisher.publish({"eventType": "AccountValidated", "status": "SUCCEEDED"})
    next_url = sqs.get_queue_url(QueueName=settings.sqs_next_queue_name)["QueueUrl"]
    outbound = sqs.receive_message(QueueUrl=next_url).get("Messages", [])
    assert len(outbound) == 1
