"""Intake API router."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.use_cases import IntakeRequestUseCase
from app.domain.models import GovernanceRequest
from app.infrastructure.api.dependencies import get_intake_use_case
from app.infrastructure.api.schemas import IntakeRequestSchema, IntakeResponseSchema

router = APIRouter(tags=["intake"])


@router.post(
    "/intake",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IntakeResponseSchema,
)
async def intake_request(
    request: IntakeRequestSchema,
    use_case: IntakeRequestUseCase = Depends(get_intake_use_case),
) -> IntakeResponseSchema:
    domain_req = GovernanceRequest(
        request_id=request.request_id or f"req-{uuid.uuid4().hex[:8]}",
        attempt_id=request.attempt_id or "attempt-0001",
        correlation_id=request.correlation_id or f"corr-{uuid.uuid4().hex[:8]}",
        producer_account_id=request.producer_account_id or "",
        consumer_account_id=request.consumer_account_id or "",
        database_name=request.database_name or "",
        table_names=request.table_names,
        iam_principal_arn=request.iam_principal_arn or "",
        permissions=request.permissions,
        s3_bucket=request.s3_bucket,
        s3_key=request.s3_key,
        action=request.action,
        fail_at_step=request.fail_at_step,
    )
    try:
        result = await use_case.execute(domain_req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return IntakeResponseSchema(
        request_id=result.request_id,
        attempt_id=result.attempt_id,
        correlation_id=result.correlation_id,
        status=result.status,
    )
