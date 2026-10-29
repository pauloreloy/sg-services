"""S3 payload storage adapter for intake service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.domain.ports import PayloadStoragePort


class S3PayloadStorageAdapter(PayloadStoragePort):
    def __init__(self, s3_client: Any) -> None:
        self._s3 = s3_client

    async def get_payload(self, bucket: str, key: str) -> dict[str, Any]:
        response = await asyncio.to_thread(
            self._s3.get_object,
            Bucket=bucket,
            Key=key,
        )
        content = await asyncio.to_thread(response["Body"].read)
        parsed = json.loads(content.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("S3 payload content is not a JSON object.")
        return parsed
