"""HTTP adapter to query checkstep-service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.domain.ports import CheckStepClientPort

logger = logging.getLogger(__name__)


class HttpCheckStepClientAdapter(CheckStepClientPort):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def check_step(
        self, request_id: str, attempt_id: str, step_name: str
    ) -> dict[str, Any]:
        url = f"{self._base_url}/internal/checkStep"
        payload = {
            "requestId": request_id,
            "attemptId": attempt_id,
            "stepName": step_name,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {
                "stepName": step_name,
                "status": "UNKNOWN",
                "statusCode": resp.status_code,
            }
