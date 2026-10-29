"""Outbound port: queue publisher.

Used by the application layer to publish the outcome of processing a message
to either the "success" or the "failure" queue.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class QueuePublisherPort(ABC):
    """Abstract contract for publishing a message to a destination queue."""

    @abstractmethod
    async def publish(self, message: Mapping[str, Any]) -> None:
        """Publish ``message`` to the configured destination queue."""
