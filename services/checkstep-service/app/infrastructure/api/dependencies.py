"""FastAPI dependency providers.

Bridges the composition root (``app.state.container``) into FastAPI's
dependency injection system, keeping route handlers thin.
"""

from __future__ import annotations

from fastapi import Request

from app.application.use_cases import GetGrantStatusUseCase


def get_grant_status_use_case(request: Request) -> GetGrantStatusUseCase:
    return request.app.state.container.get_grant_status_use_case
