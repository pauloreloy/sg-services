"""POST /checkStep route.

Given a grant_id, returns the latest processing status recorded in DynamoDB
by the sqs-consumer service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.use_cases import GetGrantStatusUseCase
from app.domain.exceptions import GrantNotFoundError
from app.infrastructure.api.dependencies import get_grant_status_use_case
from app.infrastructure.api.schemas import CheckStepRequest, CheckStepResponse

router = APIRouter(tags=["checkStep"])


@router.post(
    "/checkStep",
    response_model=CheckStepResponse,
    responses={404: {"description": "grant_id not found"}},
)
async def check_step(
    request: CheckStepRequest,
    use_case: GetGrantStatusUseCase = Depends(get_grant_status_use_case),
) -> CheckStepResponse:
    try:
        result = await use_case.execute(request.grant_id)
    except GrantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CheckStepResponse(
        grant_id=result.grant_id,
        status=result.status,
        action=result.action,
        reason=result.reason,
        record_id=result.record_id,
        message_id=result.message_id,
        processed_at=result.processed_at,
    )
