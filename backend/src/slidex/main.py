"""FastAPI app factory. Run with `uv run slidex serve` (binds 127.0.0.1 only)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from slidex.api import files, health, runs
from slidex.api.deps import AppContext
from slidex.core.config import Settings, get_settings
from slidex.core.errors import install_error_handlers

API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ctx: AppContext = app.state.ctx
        ctx.worker.start()
        try:
            yield
        finally:
            ctx.worker.stop()
            ctx.db.dispose()

    app = FastAPI(
        title="Slide Explainer API",
        version=API_VERSION,
        lifespan=lifespan,
        description="Local API for feature 001-slide-explainer. See specs/.../contracts.",
    )
    app.state.ctx = AppContext.build(settings)
    install_error_handlers(app)
    for router in (health.router, files.router, runs.router):
        app.include_router(router)
    return app
