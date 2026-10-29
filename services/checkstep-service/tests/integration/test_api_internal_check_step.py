"""Integration tests for POST /internal/checkStep and ADR queries."""

from __future__ import annotations

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.infrastructure.config import Settings
from app.infrastructure.container import build_container
from main import create_app

AWS_REGION = "us-east-1"
TABLE_NAME = "sg-share-governance"


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

    settings = Settings(
        aws_region=AWS_REGION,
        aws_endpoint_url=None,
        dynamodb_governance_table_name=TABLE_NAME,
    )
    app = create_app()
    app.state.container = build_container(settings)
    return TestClient(app)


def test_internal_check_step_succeeded(client: TestClient, aws_mock):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(
        Item={
            "PK": "REQUEST#req-999",
            "SK": "STEP#RESOURCE_LINKS#ATTEMPT#attempt-0001",
            "requestId": "req-999",
            "attemptId": "attempt-0001",
            "stepName": "RESOURCE_LINKS",
            "status": "SUCCEEDED",
            "startedAt": "2026-10-28T22:58:00Z",
            "completedAt": "2026-10-28T22:58:04Z",
        }
    )

    resp = client.post(
        "/internal/checkStep",
        json={
            "requestId": "req-999",
            "attemptId": "attempt-0001",
            "stepName": "RESOURCE_LINKS",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCEEDED"
    assert data["requestId"] == "req-999"
    assert data["stepName"] == "RESOURCE_LINKS"


def test_internal_check_step_failed(client: TestClient, aws_mock):
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(
        Item={
            "PK": "REQUEST#req-err",
            "SK": "STEP#PERMISSIONS#ATTEMPT#attempt-0001",
            "requestId": "req-err",
            "attemptId": "attempt-0001",
            "stepName": "PERMISSIONS",
            "status": "FAILED",
            "errorCode": "PERMISSION_DENIED",
            "message": "Access denied granting Lake Formation permissions.",
        }
    )

    resp = client.post(
        "/checkStep",
        json={
            "requestId": "req-err",
            "attemptId": "attempt-0001",
            "stepName": "PERMISSIONS",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["errorCode"] == "PERMISSION_DENIED"


def test_internal_check_step_not_found(client: TestClient, aws_mock):
    resp = client.post(
        "/internal/checkStep",
        json={
            "requestId": "non-existent",
            "stepName": "ACCOUNT_VALIDATION",
        },
    )
    assert resp.status_code == 404
