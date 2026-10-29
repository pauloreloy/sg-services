"""DynamoDB adapter implementing the :class:`StepStatusRepositoryPort`."""

from __future__ import annotations

import asyncio
from typing import Any

from app.domain.models import StepStatusRecord
from app.domain.ports import StepStatusRepositoryPort


class DynamoDbStepStatusRepository(StepStatusRepositoryPort):
    """Reads step execution records from DynamoDB (PK: REQUEST#<requestId>, SK: STEP#<stepName>#ATTEMPT#<attemptId>)."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    async def find_step_status(
        self, request_id: str, step_name: str, attempt_id: str | None = None
    ) -> StepStatusRecord | None:
        pk = f"REQUEST#{request_id}"

        # If attempt_id is provided, fetch directly by primary key
        if attempt_id:
            sk = f"STEP#{step_name}#ATTEMPT#{attempt_id}"
            response = await asyncio.to_thread(
                self._table.get_item,
                Key={"PK": pk, "SK": sk},
            )
            item = response.get("Item")
            if item:
                return self._to_domain(item)
            return None

        # If attempt_id was omitted, check META item first to find currentAttemptId
        meta_response = await asyncio.to_thread(
            self._table.get_item,
            Key={"PK": pk, "SK": "META"},
        )
        meta_item = meta_response.get("Item")
        if meta_item and "currentAttemptId" in meta_item:
            current_attempt = meta_item["currentAttemptId"]
            sk = f"STEP#{step_name}#ATTEMPT#{current_attempt}"
            response = await asyncio.to_thread(
                self._table.get_item,
                Key={"PK": pk, "SK": sk},
            )
            item = response.get("Item")
            if item:
                return self._to_domain(item)

        # Fallback: query all steps matching prefix and pick latest
        response = await asyncio.to_thread(
            self._table.query,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": pk,
                ":prefix": f"STEP#{step_name}#",
            },
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_domain(items[0])

    @staticmethod
    def _to_domain(item: dict[str, Any]) -> StepStatusRecord:
        return StepStatusRecord(
            request_id=item.get("requestId", ""),
            attempt_id=item.get("attemptId", ""),
            step_name=item.get("stepName", ""),
            status=item.get("status", "UNKNOWN"),
            started_at=item.get("startedAt"),
            completed_at=item.get("completedAt"),
            error_code=item.get("errorCode"),
            message=item.get("message"),
        )
