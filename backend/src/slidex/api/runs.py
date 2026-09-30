from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from slidex.api.deps import AppContext, get_ctx
from slidex.api.schemas import Run
from slidex.core.errors import SlidexError
from slidex.graph.runs import run_out

router = APIRouter(tags=["runs"])

Ctx = Annotated[AppContext, Depends(get_ctx)]


@router.get("/runs/{run_id}", operation_id="getRun")
def get_run(run_id: str, ctx: Ctx) -> Run:
    return run_out(ctx.db, ctx.runs.get(run_id))


@router.post("/runs/{run_id}/resume", operation_id="resumeRun", status_code=202)
def resume_run(run_id: str, ctx: Ctx) -> Run:
    run = ctx.runs.get(run_id)
    if ctx.worker.is_active(run_id) or run.status == "completed":
        raise SlidexError("invalid_state", f"Run is {run.status}; nothing to resume.")
    resumer = ctx.worker.resumer_for(run.kind)
    if resumer is None:
        raise SlidexError("invalid_state", f"Runs of kind '{run.kind}' cannot be resumed.")
    ctx.runs.stage(run_id, run.stage or "resuming")
    ctx.worker.submit(run_id, resumer(run_id))
    return run_out(ctx.db, ctx.runs.get(run_id))


@router.post("/runs/{run_id}/cancel", operation_id="cancelRun", status_code=202)
def cancel_run(run_id: str, ctx: Ctx) -> Run:
    run = ctx.runs.get(run_id)
    if run.status in ("completed", "failed", "cancelled"):
        raise SlidexError("invalid_state", f"Run is already {run.status}.")
    ctx.worker.cancel(run_id)
    ctx.runs.finish(run_id, "cancelled")
    return run_out(ctx.db, ctx.runs.get(run_id))


@router.get(
    "/decks/{deck_id}/events",
    operation_id="streamDeckEvents",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Event stream"}},
)
async def stream_deck_events(deck_id: str, request: Request, ctx: Ctx) -> EventSourceResponse:
    queue = ctx.events.subscribe(deck_id)

    async def gen() -> AsyncIterator[dict[str, Any]]:
        try:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    continue
                yield {"event": event.event, "data": event.model_dump_json()}
        finally:
            ctx.events.unsubscribe(deck_id, queue)

    return EventSourceResponse(gen(), ping=15)
