"""Composition root for intake service."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import IntakeRequestUseCase
from app.infrastructure.adapters import (
    DynamoDbStepRepositoryAdapter,
    S3PayloadStorageAdapter,
    SqsQueuePublisherAdapter,
)
from app.infrastructure.aws_clients import (
    build_dynamodb_resource,
    build_s3_client,
    build_sqs_client,
)
from app.infrastructure.config import Settings, get_settings


@dataclass
class Container:
    settings: Settings
    intake_use_case: IntakeRequestUseCase


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    sqs_client = build_sqs_client(settings)
    dynamodb_resource = build_dynamodb_resource(settings)
    s3_client = build_s3_client(settings)

    repository = DynamoDbStepRepositoryAdapter(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_table_name,
    )
    publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs_client, queue_name=settings.sqs_first_queue_name
    )
    storage = S3PayloadStorageAdapter(s3_client=s3_client)

    use_case = IntakeRequestUseCase(
        repository=repository,
        publisher=publisher,
        storage=storage,
    )

    return Container(settings=settings, intake_use_case=use_case)
