"""DynamoDB adapter implementing the :class:`GrantStatusRepositoryPort`.

Queries the `grant_id-processed_at-index` GSI (partition key: grant_id, sort
key: processed_at) so that the latest record for a grant_id can be fetched in
a single, efficient ``Query`` call (O(1) lookup, no table scan), instead of
scanning the whole table and filtering in-memory.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.domain.enums import ProcessingStatus
from app.domain.models import GrantStatus
from app.domain.ports import GrantStatusRepositoryPort


class DynamoDbGrantStatusRepository(GrantStatusRepositoryPort):
    """Reads grant processing status from a DynamoDB table via a GSI."""

    def __init__(self, dynamodb_resource: Any, table_name: str, index_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)
        self._index_name = index_name

    async def find_latest_by_grant_id(self, grant_id: str) -> GrantStatus | None:
        response = await asyncio.to_thread(
            self._table.query,
            IndexName=self._index_name,
            KeyConditionExpression="grant_id = :gid",
            ExpressionAttributeValues={":gid": grant_id},
            ScanIndexForward=False,  # descending by processed_at -> most recent first
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_domain(items[0])

    @staticmethod
    def _to_domain(item: dict) -> GrantStatus:
        return GrantStatus(
            grant_id=item["grant_id"],
            record_id=item["record_id"],
            message_id=item["message_id"],
            action=item["action"],
            status=ProcessingStatus(item["status"]),
            processed_at=datetime.fromisoformat(item["processed_at"]),
            reason=item.get("reason"),
        )
