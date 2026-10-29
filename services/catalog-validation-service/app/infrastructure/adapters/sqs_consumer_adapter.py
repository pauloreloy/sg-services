"""SQS consumer adapter for catalog validation service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.domain.models import IncomingMessage
from app.domain.ports import QueueConsumerPort
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class SqsQueueConsumerAdapter(QueueConsumerPort):
    def __init__(self, sqs_client: Any, settings: Settings, queue_name: str) -> None:
        self._sqs = sqs_client
        self._settings = settings
        self._queue_name = queue_name
        self._queue_url: str | None = None

    async def _get_queue_url(self) -> str:
        if self._queue_url is None:
            response = await asyncio.to_thread(
                self._sqs.get_queue_url, QueueName=self._queue_name
            )
            self._queue_url = response["QueueUrl"]
        return self._queue_url

    async def receive_messages(self) -> list[IncomingMessage]:
        queue_url = await self._get_queue_url()
        response = await asyncio.to_thread(
            self._sqs.receive_message,
            QueueUrl=queue_url,
            MaxNumberOfMessages=self._settings.sqs_max_messages,
            WaitTimeSeconds=self._settings.sqs_wait_time_seconds,
            VisibilityTimeout=self._settings.sqs_visibility_timeout,
        )

        messages = []
        for raw in response.get("Messages", []):
            payload = self._parse_body(raw["Body"], raw["MessageId"])
            messages.append(
                IncomingMessage(
                    message_id=raw["MessageId"],
                    receipt_handle=raw["ReceiptHandle"],
                    payload=payload,
                )
            )
        return messages

    async def acknowledge(self, message: IncomingMessage) -> None:
        queue_url = await self._get_queue_url()
        await asyncio.to_thread(
            self._sqs.delete_message,
            QueueUrl=queue_url,
            ReceiptHandle=message.receipt_handle,
        )

    @staticmethod
    def _parse_body(body: str, message_id: str) -> dict:
        try:
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise ValueError("Message body is not a JSON object.")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Message id=%s has non-JSON body: %s", message_id, exc)
            return {"raw_body": body}
