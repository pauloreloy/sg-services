"""SQS publisher adapter for intake service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from app.domain.ports import QueuePublisherPort


class SqsQueuePublisherAdapter(QueuePublisherPort):
    def __init__(self, sqs_client: Any, queue_name: str) -> None:
        self._sqs = sqs_client
        self._queue_name = queue_name
        self._queue_url: str | None = None

    async def _get_queue_url(self) -> str:
        if self._queue_url is None:
            response = await asyncio.to_thread(
                self._sqs.get_queue_url, QueueName=self._queue_name
            )
            self._queue_url = response["QueueUrl"]
        return self._queue_url

    async def publish(self, message: Mapping[str, Any]) -> None:
        queue_url = await self._get_queue_url()
        await asyncio.to_thread(
            self._sqs.send_message,
            QueueUrl=queue_url,
            MessageBody=json.dumps(message, default=str),
        )
