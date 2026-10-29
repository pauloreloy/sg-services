"""Diagnose router."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.domain.models import TerminalEventMessage
from app.infrastructure.api.schemas import (
    DiagnoseRequestSchema,
    DiagnoseResponseSchema,
)

router = APIRouter(tags=["diagnostic"])


@router.post("/diagnose", response_model=DiagnoseResponseSchema)
async def diagnose(request: DiagnoseRequestSchema, req: Request) -> DiagnoseResponseSchema:
    use_case = req.app.state.container.diagnostic_use_case
    event = TerminalEventMessage(
        message_id="manual",
        receipt_handle="manual",
        payload={
            "requestId": request.request_id,
            "attemptId": request.attempt_id,
            "terminalStatus": request.terminal_status,
        },
    )
    outcome = await use_case.execute(event)
    return DiagnoseResponseSchema(
        request_id=outcome.request_id,
        attempt_id=outcome.attempt_id,
        terminal_status=outcome.terminal_status,
        steps_evaluated=outcome.steps_evaluated,
        first_failed_step=outcome.first_failed_step,
        step_functions_execution_arn=outcome.step_functions_execution_arn,
        sns_published=outcome.sns_published,
    )
