"""FastAPI entrypoint for share-acceptance-service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    container = build_container()
    app.state.container = container

    container.worker.start()
    try:
        yield
    finally:
        await container.worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Microservice that accepts cross-account RAM shares conditionally.",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    return app


app = create_app()
