"""Integration tests for the AWS adapters, using moto to mock AWS locally.

These tests do not require Docker/LocalStack; they validate that the
adapters correctly use the boto3 API against an in-memory mocked AWS backend.
"""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from app.domain.enums import ProcessingStatus
from app.domain.models import IncomingMessage, ProcessingRecord
from app.infrastructure.adapters import (
    DynamoDbProcessingRecordRepository,
    SqsQueueConsumerAdapter,
    SqsQueuePublisherAdapter,
)
from app.infrastructure.config import Settings

AWS_REGION = "us-east-1"


@pytest.fixture
def aws_mock():
    """Activate moto's AWS mocking for the duration of a test.

    Using a fixture (rather than the ``@mock_aws`` decorator directly on the
    test function) keeps the test functions recognizable as plain coroutines
    for pytest-asyncio.
    """
    with mock_aws():
        yield


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_region=AWS_REGION,
        aws_endpoint_url=None,
        sqs_source_queue_name="sg-share-queue",
        sqs_success_queue_name="sg-share-success-queue",
        sqs_failure_queue_name="sg-share-failure-queue",
        sqs_wait_time_seconds=0,
        dynamodb_table_name="sg-share-processing-records",
    )


@pytest.mark.asyncio
async def test_sqs_consumer_and_publisher_round_trip(aws_mock, settings: Settings):
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    sqs.create_queue(QueueName=settings.sqs_source_queue_name)
    sqs.create_queue(QueueName=settings.sqs_success_queue_name)

    consumer = SqsQueueConsumerAdapter(
        sqs_client=sqs, settings=settings, queue_name=settings.sqs_source_queue_name
    )
    publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs, queue_name=settings.sqs_success_queue_name
    )

    queue_url = sqs.get_queue_url(QueueName=settings.sqs_source_queue_name)["QueueUrl"]
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps({"action": "success"}))

    messages = await consumer.receive_messages()
    assert len(messages) == 1
    assert messages[0].payload == {"action": "success"}

    await consumer.acknowledge(messages[0])
    remaining = sqs.receive_message(QueueUrl=queue_url).get("Messages", [])
    assert remaining == []

    await publisher.publish({"status": "SUCCESS", "message_id": messages[0].message_id})
    success_queue_url = sqs.get_queue_url(QueueName=settings.sqs_success_queue_name)["QueueUrl"]
    published = sqs.receive_message(QueueUrl=success_queue_url)["Messages"]
    assert json.loads(published[0]["Body"])["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_dynamodb_repository_persists_record(aws_mock, settings: Settings):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    dynamodb.create_table(
        TableName=settings.dynamodb_table_name,
        KeySchema=[{"AttributeName": "record_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "record_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    repository = DynamoDbProcessingRecordRepository(
        dynamodb_resource=dynamodb, table_name=settings.dynamodb_table_name
    )

    message = IncomingMessage(
        message_id="msg-1",
        receipt_handle="rh",
        payload={"action": "success", "grant_id": "grant-abc"},
    )
    record = ProcessingRecord.success(message, action="success")
    await repository.save(record)

    table = dynamodb.Table(settings.dynamodb_table_name)
    item = table.get_item(Key={"record_id": record.record_id})["Item"]
    assert item["status"] == ProcessingStatus.SUCCESS.value
    assert item["message_id"] == "msg-1"
    assert item["grant_id"] == "grant-abc"


@pytest.mark.asyncio
async def test_dynamodb_repository_omits_grant_id_when_absent(aws_mock, settings: Settings):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    dynamodb.create_table(
        TableName=settings.dynamodb_table_name,
        KeySchema=[{"AttributeName": "record_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "record_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    repository = DynamoDbProcessingRecordRepository(
        dynamodb_resource=dynamodb, table_name=settings.dynamodb_table_name
    )

    message = IncomingMessage(message_id="msg-2", receipt_handle="rh", payload={"action": "fail"})
    record = ProcessingRecord.failure(message, action="fail", reason="explicit fail")
    await repository.save(record)

    table = dynamodb.Table(settings.dynamodb_table_name)
    item = table.get_item(Key={"record_id": record.record_id})["Item"]
    assert "grant_id" not in item
