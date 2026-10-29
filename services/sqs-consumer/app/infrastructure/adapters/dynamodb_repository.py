"""DynamoDB adapter implementing the :class:`ProcessingRecordRepositoryPort`."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.domain.models import ProcessingRecord
from app.domain.ports import ProcessingRecordRepositoryPort


class DynamoDbProcessingRecordRepository(ProcessingRecordRepositoryPort):
    """Persists :class:`ProcessingRecord` entities into a DynamoDB table."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    async def save(self, record: ProcessingRecord) -> None:
        item = {
            "record_id": record.record_id,
            "message_id": record.message_id,
            "action": record.action,
            "status": record.status.value,
            "reason": record.reason,
            # DynamoDB has no native dict-of-Any guarantee for nested types,
            # so the payload is stored as a JSON string for robustness.
            "payload": json.dumps(dict(record.payload), default=str),
            "processed_at": record.processed_at.isoformat(),
        }
        if record.grant_id is not None:
            # Only set the attribute when present so the GSI on grant_id stays
            # sparse (records without a grant_id are simply not indexed).
            item["grant_id"] = record.grant_id
        await asyncio.to_thread(self._table.put_item, Item=item)
