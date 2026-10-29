"""POST /checkStep and POST /internal/checkStep routes.

Supports:
- ADR Section 6.2 query by requestId, stepName, and optional attemptId.
- Legacy query by grant_id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.use_cases import GetGrantStatusUseCase, GetStepStatusUseCase
from app.domain.exceptions import GrantNotFoundError, StepNotFoundError
from app.infrastructure.api.dependencies import (
    get_grant_status_use_case,
    get_step_status_use_case,
)
from app.infrastructure.api.schemas import CheckStepRequest, CheckStepResponse

router = APIRouter(tags=["checkStep"])


async def _handle_check_step(
    request: CheckStepRequest,
    grant_use_case: GetGrantStatusUseCase,
    step_use_case: GetStepStatusUseCase,
) -> CheckStepResponse:
    # 1. ADR step status query
    if request.request_id and request.step_name:
        try:
            step_record = await step_use_case.execute(
                request_id=request.request_id,
                step_name=request.step_name,
                attempt_id=request.attempt_id,
            )
            return CheckStepResponse(
                request_id=step_record.request_id,
                attempt_id=step_record.attempt_id,
                step_name=step_record.step_name,
                status=step_record.status,
                started_at=step_record.started_at,
                completed_at=step_record.completed_at,
                error_code=step_record.error_code,
                message=step_record.message,
            )
        except StepNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # 2. Legacy grant_id query
    if request.grant_id:
        try:
            result = await grant_use_case.execute(request.grant_id)
            return CheckStepResponse(
                grant_id=result.grant_id,
                status=result.status.value,
                action=result.action,
                reason=result.reason,
                record_id=result.record_id,
                message_id=result.message_id,
                processed_at=result.processed_at,
            )
        except GrantNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Must provide either 'grant_id' or both 'requestId' and 'stepName'.",
    )


@router.post(
    "/checkStep",
    response_model=CheckStepResponse,
    responses={404: {"description": "Resource not found"}},
)
async def check_step(
    request: CheckStepRequest,
    grant_use_case: GetGrantStatusUseCase = Depends(get_grant_status_use_case),
    step_use_case: GetStepStatusUseCase = Depends(get_step_status_use_case),
) -> CheckStepResponse:
    return await _handle_check_step(request, grant_use_case, step_use_case)


@router.post(
    "/internal/checkStep",
    response_model=CheckStepResponse,
    responses={404: {"description": "Resource not found"}},
)
async def internal_check_step(
    request: CheckStepRequest,
    grant_use_case: GetGrantStatusUseCase = Depends(get_grant_status_use_case),
    step_use_case: GetStepStatusUseCase = Depends(get_step_status_use_case),
) -> CheckStepResponse:
    return await _handle_check_step(request, grant_use_case, step_use_case)
