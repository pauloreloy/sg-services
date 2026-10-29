"""FastAPI entrypoint for intake-service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.api.health import router as health_router
from app.infrastructure.api.intake import router as intake_router
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
        description="Entrypoint intake microservice for AWS data governance platform (Account C).",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(intake_router)
    return app


app = create_app()
