"""Composition root: wires adapters and use cases together.

This is the only module allowed to know about every concrete adapter; the
rest of the application depends solely on the domain ports.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import GetGrantStatusUseCase, GetStepStatusUseCase
from app.infrastructure.adapters import (
    DynamoDbGrantStatusRepository,
    DynamoDbStepStatusRepository,
)
from app.infrastructure.aws_clients import build_dynamodb_resource
from app.infrastructure.config import Settings, get_settings


@dataclass
class Container:
    """Holds every wired component needed to serve HTTP requests."""

    settings: Settings
    get_grant_status_use_case: GetGrantStatusUseCase
    get_step_status_use_case: GetStepStatusUseCase


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    dynamodb_resource = build_dynamodb_resource(settings)
    grant_repository = DynamoDbGrantStatusRepository(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_table_name,
        index_name=settings.dynamodb_grant_id_index_name,
    )
    step_repository = DynamoDbStepStatusRepository(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_governance_table_name,
    )

    grant_use_case = GetGrantStatusUseCase(repository=grant_repository)
    step_use_case = GetStepStatusUseCase(repository=step_repository)

    return Container(
        settings=settings,
        get_grant_status_use_case=grant_use_case,
        get_step_status_use_case=step_use_case,
    )
