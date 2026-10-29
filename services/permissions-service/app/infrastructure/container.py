"""Composition root for permissions service."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import GrantPermissionsUseCase
from app.infrastructure.adapters import (
    DynamoDbStepRepositoryAdapter,
    SqsQueueConsumerAdapter,
    SqsQueuePublisherAdapter,
)
from app.infrastructure.aws_clients import build_dynamodb_resource, build_sqs_client
from app.infrastructure.config import Settings, get_settings
from app.workers import SqsConsumerWorker


@dataclass
class Container:
    settings: Settings
    worker: SqsConsumerWorker


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    sqs_client = build_sqs_client(settings)
    dynamodb_resource = build_dynamodb_resource(settings)

    repository = DynamoDbStepRepositoryAdapter(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_table_name,
    )
    completed_publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs_client, queue_name=settings.sqs_completed_queue_name
    )
    failure_publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs_client, queue_name=settings.sqs_failure_queue_name
    )
    consumer = SqsQueueConsumerAdapter(
        sqs_client=sqs_client,
        settings=settings,
        queue_name=settings.sqs_source_queue_name,
    )

    use_case = GrantPermissionsUseCase(
        repository=repository,
        completed_publisher=completed_publisher,
        failure_publisher=failure_publisher,
    )
    worker = SqsConsumerWorker(consumer=consumer, use_case=use_case, settings=settings)

    return Container(settings=settings, worker=worker)
