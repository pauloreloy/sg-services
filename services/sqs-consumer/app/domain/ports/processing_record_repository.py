"""Outbound port: processing record repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import ProcessingRecord


class ProcessingRecordRepositoryPort(ABC):
    """Abstract contract for persisting :class:`ProcessingRecord` entities."""

    @abstractmethod
    async def save(self, record: ProcessingRecord) -> None:
        """Persist the processing record (e.g. into DynamoDB)."""
