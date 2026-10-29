"""Shared AWS clients factories."""

from shared.aws_clients.factories import (
    build_boto3_client,
    build_boto3_resource,
    get_aws_config,
)

__all__ = ["build_boto3_client", "build_boto3_resource", "get_aws_config"]
