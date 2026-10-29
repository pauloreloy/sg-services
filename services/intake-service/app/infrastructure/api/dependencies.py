"""FastAPI dependency providers for intake service."""

from fastapi import Request

from app.application.use_cases import IntakeRequestUseCase


def get_intake_use_case(request: Request) -> IntakeRequestUseCase:
    return request.app.state.container.intake_use_case
