"""Integration tests for Intake API using moto."""

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.infrastructure.config import Settings
from app.infrastructure.container import build_container
from main import create_app

AWS_REGION = "us-east-1"
TABLE_NAME = "sg-share-governance"
QUEUE_NAME = "access-validation"


@pytest.fixture
def aws_mock():
    with mock_aws():
        yield


@pytest.fixture
def client(aws_mock) -> TestClient:
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    dynamodb.create_table(
        TableName=TABLE_NAME,
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

    sqs = boto3.client("sqs", region_name=AWS_REGION)
    sqs.create_queue(QueueName=QUEUE_NAME)

    settings = Settings(
        aws_region=AWS_REGION,
        aws_endpoint_url=None,
        dynamodb_table_name=TABLE_NAME,
        sqs_first_queue_name=QUEUE_NAME,
    )

    app = create_app()
    app.state.container = build_container(settings)
    return TestClient(app)


def test_post_intake(client: TestClient, aws_mock):
    resp = client.post(
        "/intake",
        json={
            "producerAccountId": "111122223333",
            "consumerAccountId": "444455556666",
            "databaseName": "sales_db",
            "tableNames": ["orders"],
            "iamPrincipalArn": "arn:aws:iam::444455556666:role/DataAnalyst",
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "ACCEPTED"
    assert "requestId" in data
    assert "attemptId" in data
