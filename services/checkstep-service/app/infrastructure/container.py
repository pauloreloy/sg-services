"""Composition root: wires adapters and use cases together.

This is the only module allowed to know about every concrete adapter; the
rest of the application depends solely on the domain ports.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases import GetGrantStatusUseCase
from app.infrastructure.adapters import DynamoDbGrantStatusRepository
from app.infrastructure.aws_clients import build_dynamodb_resource
from app.infrastructure.config import Settings, get_settings


@dataclass
class Container:
    """Holds every wired component needed to serve HTTP requests."""

    settings: Settings
    get_grant_status_use_case: GetGrantStatusUseCase


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    dynamodb_resource = build_dynamodb_resource(settings)
    repository = DynamoDbGrantStatusRepository(
        dynamodb_resource=dynamodb_resource,
        table_name=settings.dynamodb_table_name,
        index_name=settings.dynamodb_grant_id_index_name,
    )
    use_case = GetGrantStatusUseCase(repository=repository)

    return Container(settings=settings, get_grant_status_use_case=use_case)
