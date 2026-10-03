"""The deck pipeline as a LangGraph state graph — the agent's coordination layer.

    extract → interpret → topics → [PAUSE: confirm research + estimate]
      → research → disagree → [PAUSE: approve sources] → process_sources → END

* Checkpointed to data/checkpoints.db (thread "deck:<id>"), so a crashed run resumes at the
  last finished node (FR-030). Every node is idempotent: model calls are cached and work
  already stored is skipped, so re-running a node never pays twice.
* The two pauses use `interrupt()`; the API resumes them with `Command(resume=...)`.
* Each API action is one Run: extract (start → first pause), research (→ second pause),
  process_sources (→ end). Run/stage/progress/cost are reported via RunTracker + SSE.
"""

from __future__ import annotations

import asyncio
import logging
from itertools import pairwise
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.books.figures import capture_figures
from slidex.books.raptor import build_tree
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, DeckSource, Source
from slidex.graph.events import DeckEvent
from slidex.research.agent import research_deck
from slidex.research.disagree import detect_disagreements
from slidex.understand.extract import extract_slides
from slidex.understand.interpret import interpret_vague
from slidex.understand.topics import consolidate_topics

log = logging.getLogger(__name__)


class DeckState(TypedDict):
    deck_id: str
    topic_ids: NotRequired[list[str] | None]


Update = dict[str, Any]


def _run_id(config: RunnableConfig) -> str:
    return str(config.get("configurable", {})["run_id"])


def set_deck_status(ctx: AppContext, deck_id: str, status: str) -> None:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        if deck.status != "failed":
            deck.previous_status = deck.status
        deck.status = status
        deck.error = None
    ctx.events.publish(DeckEvent(event="deck.status", deck_id=deck_id, message=status))


def _book_path(ctx: AppContext, source_id: str) -> Path:
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None and src.file_hash
        return ctx.files.path(src.file_hash)


def build_graph(ctx: AppContext) -> StateGraph[DeckState]:
    def progress(run_id: str, lo: float, hi: float) -> Any:
        return lambda done, total: ctx.runs.progress(run_id, lo + (hi - lo) * done / max(total, 1))

    async def extract(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        set_deck_status(ctx, state["deck_id"], "extracting")
        ctx.runs.stage(run_id, "slide_extraction", 0.0)
        await extract_slides(ctx, state["deck_id"], run_id, progress(run_id, 0.0, 0.7))
        return {}

    async def interpret(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        ctx.runs.stage(run_id, "interpretation", 0.7)
        await interpret_vague(ctx, state["deck_id"], run_id)
        return {}

    async def topics(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        ctx.runs.stage(run_id, "topics", 0.9)
        await consolidate_topics(ctx, state["deck_id"], run_id)
        set_deck_status(ctx, state["deck_id"], "ready_for_research")
        return {}

    async def confirm_research(state: DeckState, config: RunnableConfig) -> Update:
        set_deck_status(ctx, state["deck_id"], "awaiting_research_confirm")
        decision = interrupt({"type": "confirm_research", "deck_id": state["deck_id"]})
        return {"topic_ids": (decision or {}).get("topic_ids")}

    async def research(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        set_deck_status(ctx, state["deck_id"], "researching")
        ctx.runs.stage(run_id, "research_search", 0.0)
        await research_deck(
            ctx, state["deck_id"], run_id, state.get("topic_ids"), progress(run_id, 0.0, 0.85)
        )
        return {}

    async def disagree(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        ctx.runs.stage(run_id, "disagreements", 0.85)
        await detect_disagreements(ctx, state["deck_id"], run_id)
        return {}

    async def approve_sources(state: DeckState, config: RunnableConfig) -> Update:
        set_deck_status(ctx, state["deck_id"], "awaiting_source_approval")
        interrupt({"type": "approve_sources", "deck_id": state["deck_id"]})
        return {}

    async def process_sources(state: DeckState, config: RunnableConfig) -> Update:
        run_id = _run_id(config)
        deck_id = state["deck_id"]
        set_deck_status(ctx, deck_id, "processing_sources")
        ctx.runs.stage(run_id, "book_processing", 0.0)
        with ctx.db.session() as s:
            books = list(
                s.scalars(
                    select(Source.id)
                    .join(DeckSource, DeckSource.source_id == Source.id)
                    .where(
                        DeckSource.deck_id == deck_id,
                        DeckSource.approved.is_(True),
                        Source.access == "usable",
                        Source.kind == "book",
                        Source.file_hash.is_not(None),
                        Source.processing_status != "ready",
                    )
                )
            )
        for i, source_id in enumerate(books):
            ctx.events.publish(
                DeckEvent(event="source.updated", deck_id=deck_id, source_id=source_id)
            )
            await build_tree(ctx, source_id, run_id)
            ctx.runs.stage(run_id, "figure_explanation")
            await capture_figures(ctx, source_id, _book_path(ctx, source_id), run_id)
            ctx.runs.progress(run_id, (i + 1) / max(len(books), 1))
        set_deck_status(ctx, deck_id, "ready")
        return {}

    g: StateGraph[DeckState] = StateGraph(DeckState)
    nodes = [
        ("extract", extract),
        ("interpret", interpret),
        ("topics", topics),
        ("confirm_research", confirm_research),
        ("research", research),
        ("disagree", disagree),
        ("approve_sources", approve_sources),
        ("process_sources", process_sources),
    ]
    for name, fn in nodes:
        g.add_node(name, fn)
    g.add_edge(START, nodes[0][0])
    for (a, _), (b, _) in pairwise(nodes):
        g.add_edge(a, b)
    g.add_edge(nodes[-1][0], END)
    return g


async def run_graph(ctx: AppContext, deck_id: str, run_id: str, payload: Any) -> None:
    """Invoke (or resume) the deck graph for one run and record the outcome."""
    path = ctx.settings.data_path / "checkpoints.db"
    try:
        async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
            graph = build_graph(ctx).compile(checkpointer=saver)
            config: RunnableConfig = {
                "configurable": {"thread_id": f"deck:{deck_id}", "run_id": run_id}
            }
            await graph.ainvoke(payload, config)
    except asyncio.CancelledError:
        ctx.runs.finish(run_id, "cancelled")
        raise
    except SlidexError as exc:
        _fail(ctx, deck_id, run_id, exc)
    except Exception as exc:
        log.exception("deck %s run %s failed", deck_id, run_id)
        _fail(ctx, deck_id, run_id, SlidexError("internal_error", f"{type(exc).__name__}: {exc}"))
    else:
        ctx.runs.finish(run_id, "completed")


def _fail(ctx: AppContext, deck_id: str, run_id: str, exc: SlidexError) -> None:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is not None:
            if deck.status != "failed":
                deck.previous_status = deck.status
            deck.status = "failed"
            deck.error = exc.to_problem()
    ctx.runs.finish(run_id, "failed", exc)


def _require_status(ctx: AppContext, deck_id: str, allowed: tuple[str, ...]) -> Deck:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        if deck.status not in allowed:
            raise SlidexError("invalid_state", f"Deck is '{deck.status}'; expected {allowed}.")
        return deck


# ------------------------------------------------------------------ public actions


def start_extract(ctx: AppContext, deck_id: str) -> str:
    run_id = ctx.runs.create(deck_id, "extract")
    ctx.worker.submit(run_id, lambda: run_graph(ctx, deck_id, run_id, {"deck_id": deck_id}))
    return run_id


def confirm_research(
    ctx: AppContext, deck_id: str, topic_ids: list[str] | None, estimate: dict[str, Any] | None
) -> str:
    _require_status(ctx, deck_id, ("awaiting_research_confirm",))
    run_id = ctx.runs.create(
        deck_id, "research", estimate=estimate, params={"topic_ids": topic_ids}
    )
    cmd: Command[Any] = Command(resume={"topic_ids": topic_ids})
    ctx.worker.submit(run_id, lambda: run_graph(ctx, deck_id, run_id, cmd))
    return run_id


def approve_sources(ctx: AppContext, deck_id: str, estimate: dict[str, Any] | None = None) -> str:
    _require_status(ctx, deck_id, ("awaiting_source_approval",))
    run_id = ctx.runs.create(deck_id, "process_sources", estimate=estimate)
    cmd: Command[Any] = Command(resume={"approved": True})
    ctx.worker.submit(run_id, lambda: run_graph(ctx, deck_id, run_id, cmd))
    return run_id


def register_resumers(ctx: AppContext) -> None:
    """After a crash, `POST /runs/{id}/resume` continues from the last checkpoint."""

    def resumer(run_id: str) -> Any:
        run = ctx.runs.get(run_id)
        return lambda: run_graph(ctx, run.deck_id, run_id, None)

    for kind in ("extract", "research", "process_sources"):
        ctx.worker.register_resumer(kind, resumer)
