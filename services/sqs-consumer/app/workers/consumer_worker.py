"""Background worker that continuously polls the source SQS queue.

Only unexpected *technical* errors (AWS/network/DB failures) prevent a
message from being acknowledged, so that it can be retried / routed to a DLQ
by SQS's own redrive policy. Business failures (action == "fail", invalid
payload, etc.) are still acknowledged, since they were handled successfully by
the use case (persisted + published to the failure queue).
"""

from __future__ import annotations

import asyncio
import logging

from app.application.use_cases import ProcessMessageUseCase
from app.domain.ports import QueueConsumerPort
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class SqsConsumerWorker:
    """Drives the polling loop: receive -> process -> acknowledge."""

    def __init__(
        self,
        consumer: QueueConsumerPort,
        use_case: ProcessMessageUseCase,
        settings: Settings,
    ) -> None:
        self._consumer = consumer
        self._use_case = use_case
        self._settings = settings
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="sqs-consumer-worker")
        logger.info("SQS consumer worker started.")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None
        logger.info("SQS consumer worker stopped.")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                messages = await self._consumer.receive_messages()
            except Exception:  # noqa: BLE001 - must keep the loop alive
                logger.exception("Failed to receive messages from the source queue.")
                await self._sleep()
                continue

            if not messages:
                await self._sleep()
                continue

            for message in messages:
                await self._handle_message(message)

    async def _handle_message(self, message) -> None:
        try:
            await self._use_case.execute(message)
        except Exception:  # noqa: BLE001 - technical failure, do not ack
            logger.exception(
                "Technical failure while processing message id=%s. "
                "Message will NOT be acknowledged and will be retried.",
                message.message_id,
            )
            return

        try:
            await self._consumer.acknowledge(message)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to acknowledge (delete) message id=%s after processing.",
                message.message_id,
            )

    async def _sleep(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_event.wait(), timeout=self._settings.sqs_poll_interval_seconds
            )
        except TimeoutError:
            pass
