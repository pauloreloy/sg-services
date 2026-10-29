"""Step Functions invoker adapter."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.domain.ports import StepFunctionsInvokerPort

logger = logging.getLogger(__name__)


class StepFunctionsInvokerAdapter(StepFunctionsInvokerPort):
    def __init__(self, sfn_client: Any) -> None:
        self._sfn = sfn_client
        self._state_machine_arn: str | None = None

    async def _get_state_machine_arn(self, state_machine_name: str) -> str | None:
        if self._state_machine_arn:
            return self._state_machine_arn
        try:
            response = await asyncio.to_thread(self._sfn.list_state_machines)
            for sm in response.get("stateMachines", []):
                if sm.get("name") == state_machine_name:
                    self._state_machine_arn = sm["stateMachineArn"]
                    return self._state_machine_arn
        except Exception as exc:
            logger.warning("Could not list state machines: %s", exc)
        return None

    async def start_execution(
        self, state_machine_name: str, execution_name: str, input_payload: dict[str, Any]
    ) -> str | None:
        arn = await self._get_state_machine_arn(state_machine_name)
        if not arn:
            logger.warning("State machine %s not found. Skipping AWS Step Functions invoke.", state_machine_name)
            return None

        try:
            response = await asyncio.to_thread(
                self._sfn.start_execution,
                stateMachineArn=arn,
                name=execution_name,
                input=json.dumps(input_payload, default=str),
            )
            return response.get("executionArn")
        except Exception as exc:
            logger.warning("Failed to start Step Functions execution: %s", exc)
            return None
