"""FastAPI app factory. Run with `uv run slidex serve` (binds 127.0.0.1 only)."""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from slidex.api import decks, documents, files, health, learn, research, runs
from slidex.api.deps import AppContext
from slidex.core.config import Settings, get_settings
from slidex.core.errors import install_error_handlers
from slidex.db.tables import Run
from slidex.graph import deck_graph, generate_graph
from slidex.retrieval import tokens

API_VERSION = "0.1.0"


def _pause_interrupted_runs(ctx: AppContext) -> None:
    """Runs left 'running' by a crash/restart become 'paused' so the UI can offer Resume."""
    with ctx.db.session() as s:
        for run in s.scalars(select(Run).where(Run.status == "running")):
            run.status = "paused"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ctx: AppContext = app.state.ctx
        ctx.worker.start()
        deck_graph.register_resumers(ctx)
        generate_graph.register_resumers(ctx)
        _pause_interrupted_runs(ctx)
        threading.Thread(
            target=tokens.warm, args=(ctx.settings.data_path / "tiktoken",), daemon=True
        ).start()
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
    for router in (
        health.router,
        files.router,
        runs.router,
        decks.router,
        research.router,
        documents.router,
        learn.router,
    ):
        app.include_router(router)
    return app
