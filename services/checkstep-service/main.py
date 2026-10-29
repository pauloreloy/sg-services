"""FastAPI application entrypoint for the checkStep service.

Exposes:
  * POST /checkStep - given a grant_id, returns the latest processing status
    recorded in DynamoDB by the sqs-consumer service.
  * GET  /health     - liveness probe.

The container listens internally on a high, non-privileged port (see
Dockerfile/docker-compose); the host maps it to port 80.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.api.check_step import router as check_step_router
from app.infrastructure.api.health import router as health_router
from app.infrastructure.config import get_settings
from app.infrastructure.container import build_container


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    app.state.container = build_container()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Microservice that exposes POST /checkStep to query the latest "
            "processing status of a grant_id, persisted in DynamoDB by the "
            "sqs-consumer service."
        ),
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(check_step_router)
    return app


app = create_app()
