"""Factory helpers for building boto3 clients/resources."""

from __future__ import annotations

import boto3

from app.infrastructure.config import Settings


def build_boto3_session(settings: Settings) -> boto3.Session:
    return boto3.Session(
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def build_dynamodb_resource(settings: Settings):
    session = build_boto3_session(settings)
    return session.resource("dynamodb", endpoint_url=settings.aws_endpoint_url or None)
