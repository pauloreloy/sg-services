"""AWS client factories for permissions service."""

from __future__ import annotations

from typing import Any

import boto3

from app.infrastructure.config import Settings


def build_sqs_client(settings: Settings) -> Any:
    return boto3.client(
        "sqs",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_endpoint_url,
    )


def build_dynamodb_resource(settings: Settings) -> Any:
    return boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_endpoint_url,
    )
