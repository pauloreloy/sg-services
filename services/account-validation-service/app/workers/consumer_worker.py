"""Background worker that continuously polls the access-validation SQS queue."""

from __future__ import annotations

import asyncio
import logging

from app.application.use_cases import ValidateAccountUseCase
from app.domain.ports import QueueConsumerPort
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class SqsConsumerWorker:
    def __init__(
        self,
        consumer: QueueConsumerPort,
        use_case: ValidateAccountUseCase,
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
        self._task = asyncio.create_task(self._run(), name="account-validation-worker")
        logger.info("Account validation SQS worker started.")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None
        logger.info("Account validation SQS worker stopped.")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                messages = await self._consumer.receive_messages()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to receive messages from SQS queue.")
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
        except Exception:  # noqa: BLE001
            logger.exception(
                "Technical failure while validating account for message id=%s. Will retry via SQS redrive.",
                message.message_id,
            )
            return

        try:
            await self._consumer.acknowledge(message)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to acknowledge message id=%s.",
                message.message_id,
            )

    async def _sleep(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_event.wait(), timeout=self._settings.sqs_poll_interval_seconds
            )
        except TimeoutError:
            pass
