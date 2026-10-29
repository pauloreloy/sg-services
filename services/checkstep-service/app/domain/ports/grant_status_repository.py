"""Outbound port: grant status query repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import GrantStatus


class GrantStatusRepositoryPort(ABC):
    """Abstract contract for looking up the latest processing record of a grant."""

    @abstractmethod
    async def find_latest_by_grant_id(self, grant_id: str) -> GrantStatus | None:
        """Return the most recent :class:`GrantStatus` for ``grant_id``.

        Returns ``None`` when no record exists for the given grant_id.
        """
