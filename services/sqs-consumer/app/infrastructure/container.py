"""Composition root: wires adapters, use cases and the worker together.

This is the only module allowed to know about every concrete adapter; the
rest of the application depends solely on the domain ports.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import ProcessMessageUseCase
from app.infrastructure.adapters import (
    DynamoDbProcessingRecordRepository,
    SqsQueueConsumerAdapter,
    SqsQueuePublisherAdapter,
)
from app.infrastructure.aws_clients import build_dynamodb_resource, build_sqs_client
from app.infrastructure.config import Settings, get_settings
from app.workers import SqsConsumerWorker


@dataclass
class Container:
    """Holds every wired component needed to run the consumer worker."""

    settings: Settings
    worker: SqsConsumerWorker


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    sqs_client = build_sqs_client(settings)
    dynamodb_resource = build_dynamodb_resource(settings)

    repository = DynamoDbProcessingRecordRepository(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_table_name,
    )
    success_publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs_client, queue_name=settings.sqs_success_queue_name
    )
    failure_publisher = SqsQueuePublisherAdapter(
        sqs_client=sqs_client, queue_name=settings.sqs_failure_queue_name
    )
    consumer = SqsQueueConsumerAdapter(
        sqs_client=sqs_client,
        settings=settings,
        queue_name=settings.sqs_source_queue_name,
    )

    use_case = ProcessMessageUseCase(
        repository=repository,
        success_publisher=success_publisher,
        failure_publisher=failure_publisher,
    )
    worker = SqsConsumerWorker(consumer=consumer, use_case=use_case, settings=settings)

    return Container(settings=settings, worker=worker)
