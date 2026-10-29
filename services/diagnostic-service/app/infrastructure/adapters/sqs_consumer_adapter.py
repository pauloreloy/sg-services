"""SQS consumer adapter for diagnostic service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.domain.models import TerminalEventMessage
from app.domain.ports import QueueConsumerPort
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class SqsMultiQueueConsumerAdapter(QueueConsumerPort):
    def __init__(self, sqs_client: Any, settings: Settings, queue_names: list[str]) -> None:
        self._sqs = sqs_client
        self._settings = settings
        self._queue_names = queue_names
        self._queue_urls: dict[str, str] = {}

    async def _get_queue_url(self, queue_name: str) -> str:
        if queue_name not in self._queue_urls:
            response = await asyncio.to_thread(
                self._sqs.get_queue_url, QueueName=queue_name
            )
            self._queue_urls[queue_name] = response["QueueUrl"]
        return self._queue_urls[queue_name]

    async def receive_messages(self) -> list[TerminalEventMessage]:
        messages = []
        for q_name in self._queue_names:
            try:
                q_url = await self._get_queue_url(q_name)
                response = await asyncio.to_thread(
                    self._sqs.receive_message,
                    QueueUrl=q_url,
                    MaxNumberOfMessages=self._settings.sqs_max_messages,
                    WaitTimeSeconds=1,  # Fast poll across multiple queues
                    VisibilityTimeout=self._settings.sqs_visibility_timeout,
                )
                for raw in response.get("Messages", []):
                    payload = self._parse_body(raw["Body"], raw["MessageId"])
                    messages.append(
                        TerminalEventMessage(
                            message_id=raw["MessageId"],
                            receipt_handle=raw["ReceiptHandle"],
                            payload=payload,
                        )
                    )
            except Exception as exc:
                logger.debug("Polling queue %s: %s", q_name, exc)

        return messages

    async def acknowledge(self, message: TerminalEventMessage) -> None:
        for q_name in self._queue_names:
            try:
                q_url = await self._get_queue_url(q_name)
                await asyncio.to_thread(
                    self._sqs.delete_message,
                    QueueUrl=q_url,
                    ReceiptHandle=message.receipt_handle,
                )
            except Exception:
                pass

    @staticmethod
    def _parse_body(body: str, message_id: str) -> dict:
        try:
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise ValueError("Body not dict")
            return parsed
        except Exception:
            return {"raw": body}
