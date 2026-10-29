"""DynamoDB repository adapter for intake service."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.domain.ports import StepRepositoryPort


class DynamoDbStepRepositoryAdapter(StepRepositoryPort):
    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    async def save_meta(
        self,
        request_id: str,
        attempt_id: str,
        status: str,
        correlation_id: str = "",
        payload: dict[str, Any] | None = None,
        failed_step: str | None = None,
    ) -> None:
        pk = f"REQUEST#{request_id}"
        now_iso = datetime.now(UTC).isoformat()
        item: dict[str, Any] = {
            "PK": pk,
            "SK": "META",
            "requestId": request_id,
            "currentAttemptId": attempt_id,
            "status": status,
            "correlationId": correlation_id,
            "createdAt": now_iso,
            "updatedAt": now_iso,
        }
        if failed_step:
            item["failedStep"] = failed_step
        if payload is not None:
            item["payload"] = json.dumps(payload, default=str)

        await asyncio.to_thread(self._table.put_item, Item=item)
