"""Use case: process a single message received from the source queue.

Business rule
-------------
Every message payload must contain an ``action`` key:

* If ``action`` equals ``"fail"`` (case-insensitive) the message is treated
  as a business *failure*.
* Any other value (including ``"success"``) is treated as a *success*.
* A missing/empty ``action`` key, or a payload that cannot be parsed, is also
  treated as a failure (so that no message is silently dropped).

Regardless of the outcome, a :class:`~app.domain.models.ProcessingRecord` is
always persisted, and the result is always published to the corresponding
outbound queue (success queue or failure queue).
"""

from __future__ import annotations

import logging

from app.application.dto import ProcessMessageResult
from app.domain.exceptions import InvalidMessagePayloadError
from app.domain.models import FAILURE_ACTION_VALUE, IncomingMessage, ProcessingRecord
from app.domain.ports import (
    ProcessingRecordRepositoryPort,
    QueuePublisherPort,
)

logger = logging.getLogger(__name__)


class ProcessMessageUseCase:
    """Orchestrates the processing of a single incoming message."""

    def __init__(
        self,
        repository: ProcessingRecordRepositoryPort,
        success_publisher: QueuePublisherPort,
        failure_publisher: QueuePublisherPort,
    ) -> None:
        self._repository = repository
        self._success_publisher = success_publisher
        self._failure_publisher = failure_publisher

    async def execute(self, message: IncomingMessage) -> ProcessMessageResult:
        logger.info(
            "Received message id=%s payload=%s", message.message_id, dict(message.payload)
        )

        record = self._build_record(message)
        await self._repository.save(record)
        await self._publish_outcome(record)

        logger.info(
            "Processed message id=%s status=%s record_id=%s",
            message.message_id,
            record.status.value,
            record.record_id,
        )
        return ProcessMessageResult(
            message_id=message.message_id,
            status=record.status,
            record_id=record.record_id,
        )

    @staticmethod
    def _build_record(message: IncomingMessage) -> ProcessingRecord:
        try:
            action = message.ensure_has_action()
        except InvalidMessagePayloadError as exc:
            return ProcessingRecord.failure(message, action=None, reason=str(exc))

        if action == FAILURE_ACTION_VALUE:
            return ProcessingRecord.failure(
                message,
                action=action,
                reason=f"Message explicitly requested action='{FAILURE_ACTION_VALUE}'.",
            )

        return ProcessingRecord.success(message, action=action)

    async def _publish_outcome(self, record: ProcessingRecord) -> None:
        outbound_message = {
            "record_id": record.record_id,
            "message_id": record.message_id,
            "action": record.action,
            "status": record.status.value,
            "reason": record.reason,
            "grant_id": record.grant_id,
            "payload": dict(record.payload),
            "processed_at": record.processed_at.isoformat(),
        }
        publisher = self._success_publisher if record.is_success else self._failure_publisher
        await publisher.publish(outbound_message)
