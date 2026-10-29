"""Reusable AWS client and resource factories."""

from __future__ import annotations

import os
from typing import Any

import boto3


def get_aws_config(
    region_name: str | None = None,
    endpoint_url: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
) -> dict[str, Any]:
    region = region_name or os.getenv("AWS_REGION", "us-east-1")
    endpoint = endpoint_url if endpoint_url is not None else os.getenv("AWS_ENDPOINT_URL")
    access_key = access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
    secret_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")

    config: dict[str, Any] = {
        "region_name": region,
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
    }
    if endpoint:
        config["endpoint_url"] = endpoint
    return config


def build_boto3_client(service_name: str, **kwargs: Any) -> Any:
    cfg = get_aws_config(**kwargs)
    return boto3.client(service_name, **cfg)


def build_boto3_resource(service_name: str, **kwargs: Any) -> Any:
    cfg = get_aws_config(**kwargs)
    return boto3.resource(service_name, **cfg)
