"""Composition root for diagnostic service."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import RunDiagnosticUseCase
from app.infrastructure.adapters import (
    HttpCheckStepClientAdapter,
    SnsNotificationPublisherAdapter,
    SqsMultiQueueConsumerAdapter,
    StepFunctionsInvokerAdapter,
)
from app.infrastructure.aws_clients import (
    build_sns_client,
    build_sqs_client,
    build_stepfunctions_client,
)
from app.infrastructure.config import Settings, get_settings
from app.workers import SqsDiagnosticWorker


@dataclass
class Container:
    settings: Settings
    diagnostic_use_case: RunDiagnosticUseCase
    worker: SqsDiagnosticWorker


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    sqs_client = build_sqs_client(settings)
    sns_client = build_sns_client(settings)
    sfn_client = build_stepfunctions_client(settings)

    consumer = SqsMultiQueueConsumerAdapter(
        sqs_client=sqs_client,
        settings=settings,
        queue_names=[
            settings.sqs_completed_queue_name,
            settings.sqs_failed_queue_name,
        ],
    )
    sfn_invoker = StepFunctionsInvokerAdapter(sfn_client=sfn_client)
    check_client = HttpCheckStepClientAdapter(base_url=settings.checkstep_service_url)
    notifier = SnsNotificationPublisherAdapter(sns_client=sns_client)

    use_case = RunDiagnosticUseCase(
        sfn_invoker=sfn_invoker,
        check_step_client=check_client,
        notifier=notifier,
        state_machine_name=settings.sfn_state_machine_name,
        sns_topic_name=settings.sns_notifications_topic_name,
    )
    worker = SqsDiagnosticWorker(consumer=consumer, use_case=use_case, settings=settings)

    return Container(
        settings=settings,
        diagnostic_use_case=use_case,
        worker=worker,
    )
