"""DynamoDB adapter for account validation service."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.domain.ports import StepRepositoryPort


class DynamoDbStepRepositoryAdapter(StepRepositoryPort):
    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    async def save_step(
        self,
        request_id: str,
        attempt_id: str,
        step_name: str,
        status: str,
        correlation_id: str = "",
        started_at: str | None = None,
        completed_at: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        resource_ref: dict[str, Any] | None = None,
    ) -> None:
        pk = f"REQUEST#{request_id}"
        sk = f"STEP#{step_name}#ATTEMPT#{attempt_id}"
        now_iso = datetime.now(UTC).isoformat()

        item: dict[str, Any] = {
            "PK": pk,
            "SK": sk,
            "requestId": request_id,
            "attemptId": attempt_id,
            "stepName": step_name,
            "status": status,
            "startedAt": started_at or now_iso,
            "correlationId": correlation_id,
            "version": 1,
            "idempotencyKey": f"{request_id}#{attempt_id}#{step_name}",
            "updatedAt": now_iso,
        }
        if completed_at:
            item["completedAt"] = completed_at
        if error_code:
            item["errorCode"] = error_code
        if message:
            item["message"] = message
        if payload is not None:
            item["payload"] = json.dumps(payload, default=str)
        if resource_ref:
            item["resourceRef"] = resource_ref

        await asyncio.to_thread(self._table.put_item, Item=item)

    async def find_step(
        self, request_id: str, step_name: str, attempt_id: str
    ) -> dict[str, Any] | None:
        pk = f"REQUEST#{request_id}"
        sk = f"STEP#{step_name}#ATTEMPT#{attempt_id}"
        response = await asyncio.to_thread(
            self._table.get_item,
            Key={"PK": pk, "SK": sk},
        )
        return response.get("Item")

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
            "updatedAt": now_iso,
        }
        if failed_step:
            item["failedStep"] = failed_step
        if payload is not None:
            item["payload"] = json.dumps(payload, default=str)

        await asyncio.to_thread(self._table.put_item, Item=item)
