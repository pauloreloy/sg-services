"""Outbound port: queue consumer.

Defines the contract the application layer relies on to receive messages from
the source queue, without knowing anything about SQS/boto3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import IncomingMessage


class QueueConsumerPort(ABC):
    """Abstract contract for receiving and acknowledging queue messages."""

    @abstractmethod
    async def receive_messages(self) -> list[IncomingMessage]:
        """Poll the queue and return the messages currently available."""

    @abstractmethod
    async def acknowledge(self, message: IncomingMessage) -> None:
        """Mark a message as processed so it is removed from the queue."""
