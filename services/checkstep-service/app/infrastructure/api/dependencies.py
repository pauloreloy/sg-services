"""FastAPI dependency providers.

Bridges the composition root (``app.state.container``) into FastAPI's
dependency injection system, keeping route handlers thin.
"""

from __future__ import annotations

from fastapi import Request

from app.application.use_cases import GetGrantStatusUseCase, GetStepStatusUseCase


def get_grant_status_use_case(request: Request) -> GetGrantStatusUseCase:
    return request.app.state.container.get_grant_status_use_case


def get_step_status_use_case(request: Request) -> GetStepStatusUseCase:
    return request.app.state.container.get_step_status_use_case
