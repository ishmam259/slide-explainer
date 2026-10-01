"""Document generation graph: plan → explain → render (one thread per document).

Checkpointed like the deck graph; explanations are cached per slide, so resuming a crashed
generation only pays for slides that were not finished.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, DeckSource, ExplanationDocument, Slide, Source
from slidex.explain.assemble import assemble
from slidex.explain.planner import SlidePlanInput, plan_document
from slidex.explain.slide import SlideResult, explain_slide
from slidex.graph.deck_graph import set_deck_status
from slidex.graph.events import DeckEvent
from slidex.llm.schemas import ExplanationDocumentModel
from slidex.render import RENDERERS, available_formats
from slidex.retrieval.index import approved_usable_sources

log = logging.getLogger(__name__)


class GenState(TypedDict):
    document_id: str


def _cfg_run_id(config: RunnableConfig) -> str:
    return str(config.get("configurable", {})["run_id"])


def _doc(ctx: AppContext, doc_id: str) -> ExplanationDocument:
    with ctx.db.session() as s:
        doc = s.get(ExplanationDocument, doc_id)
        if doc is None:
            raise SlidexError("not_found", f"Document {doc_id} not found")
        return doc


def _update(ctx: AppContext, doc_id: str, **fields: Any) -> None:
    with ctx.db.session() as s:
        doc = s.get(ExplanationDocument, doc_id)
        assert doc is not None
        for k, v in fields.items():
            setattr(doc, k, v)
        deck_id = doc.deck_id
    ctx.events.publish(DeckEvent(event="document.updated", deck_id=deck_id, document_id=doc_id))


def build_graph(ctx: AppContext) -> StateGraph[GenState]:
    async def explain(state: GenState, config: RunnableConfig) -> dict[str, Any]:
        run_id = _cfg_run_id(config)
        doc = _doc(ctx, state["document_id"])
        _update(ctx, doc.id, status="generating", progress=0.0)
        ctx.runs.stage(run_id, "explanation", 0.0)
        with ctx.db.session() as s:
            deck = s.get(Deck, doc.deck_id)
            assert deck is not None
            slides = {
                sl.number: sl for sl in s.scalars(select(Slide).where(Slide.deck_id == deck.id))
            }
            unusable = set(
                s.scalars(
                    select(Source.id)
                    .join(DeckSource, DeckSource.source_id == Source.id)
                    .where(DeckSource.deck_id == deck.id, Source.access != "usable")
                )
            )
        plan = plan_document(
            [
                SlidePlanInput(
                    n,
                    list((sl.extraction or {}).get("concepts", [])),
                    (sl.extraction or {}).get("topic"),
                    sl.clarity == "divider",
                )
                for n, sl in slides.items()
            ],
            organization=doc.organization,
            slide_range=tuple(doc.slide_range) if doc.slide_range else None,  # type: ignore[arg-type]
        )
        source_ids = approved_usable_sources(ctx.db, deck.id)
        results: dict[int, SlideResult] = {}
        done = 0
        sem = asyncio.Semaphore(ctx.settings.concurrency)

        async def one(n: int) -> None:
            nonlocal done
            async with sem:
                results[n] = await explain_slide(
                    ctx, deck.id, slides[n], plan.slides[n], source_ids, unusable, run_id
                )
            done += 1
            frac = done / max(len(plan.order), 1)
            ctx.runs.progress(run_id, 0.9 * frac)
            _update(ctx, doc.id, progress=0.9 * frac)

        await asyncio.gather(*(one(n) for n in plan.order))
        model = assemble(
            ctx,
            deck.id,
            deck.title,
            doc.organization,
            plan,
            results,
            {n: sl.image_hash for n, sl in slides.items()},
        )
        stats = {
            "sections": len(model.sections),
            "reconstructed_slides": sum(1 for r in results.values() if r.reconstructed),
            "disagreements_shown": sum(
                1 for r in results.values() for b in r.blocks if b.type == "disagreement"
            ),
            "dropped_blocks": sum(r.dropped for r in results.values()),
        }
        _update(ctx, doc.id, content=model.model_dump(mode="json"), stats=stats)
        return {}

    async def render(state: GenState, config: RunnableConfig) -> dict[str, Any]:
        run_id = _cfg_run_id(config)
        doc = _doc(ctx, state["document_id"])
        _update(ctx, doc.id, status="rendering", progress=0.9)
        ctx.runs.stage(run_id, "render", 0.9)
        model = ExplanationDocumentModel.model_validate(doc.content)
        formats = available_formats()
        files: dict[str, str] = {}
        pending: list[str] = []
        for fmt in doc.formats:
            if fmt not in formats:
                pending.append(fmt)
                continue
            fn, ext = RENDERERS[fmt]
            data = await asyncio.to_thread(fn, model, ctx.files)
            files[fmt] = ctx.files.put_bytes(data, ext)
        stats = {**doc.stats, "pending_formats": len(pending)}
        _update(
            ctx,
            doc.id,
            files=files,
            stats=stats,
            status="ready",
            progress=1.0,
            error=None
            if not pending
            else SlidexError(
                "renderer_missing", f"Not yet available: {', '.join(pending)}"
            ).to_problem(),
        )
        return {}

    g: StateGraph[GenState] = StateGraph(GenState)
    g.add_node("explain", explain)
    g.add_node("render", render)
    g.add_edge(START, "explain")
    g.add_edge("explain", "render")
    g.add_edge("render", END)
    return g


async def run_generation(ctx: AppContext, doc_id: str, run_id: str, payload: Any) -> None:
    doc = _doc(ctx, doc_id)
    path = ctx.settings.data_path / "checkpoints.db"
    try:
        async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
            graph = build_graph(ctx).compile(checkpointer=saver)
            await graph.ainvoke(
                payload, {"configurable": {"thread_id": f"doc:{doc_id}", "run_id": run_id}}
            )
    except asyncio.CancelledError:
        ctx.runs.finish(run_id, "cancelled")
        raise
    except Exception as exc:
        err = (
            exc
            if isinstance(exc, SlidexError)
            else SlidexError("internal_error", f"{type(exc).__name__}: {exc}")
        )
        log.exception("document %s failed", doc_id)
        _update(ctx, doc_id, status="failed", error=err.to_problem())
        set_deck_status(ctx, doc.deck_id, "ready")
        ctx.runs.finish(run_id, "failed", err)
    else:
        set_deck_status(ctx, doc.deck_id, "ready")
        ctx.runs.finish(run_id, "completed")


def start_generation(
    ctx: AppContext,
    deck_id: str,
    organization: str,
    formats: list[str],
    slide_range: list[int] | None,
    estimate: dict[str, Any] | None = None,
) -> tuple[str, str]:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        if deck.status != "ready":
            raise SlidexError("invalid_state", f"Deck is '{deck.status}'; approve sources first.")
        doc = ExplanationDocument(
            deck_id=deck_id, organization=organization, formats=formats, slide_range=slide_range
        )
        s.add(doc)
        s.flush()
        doc_id = doc.id
    set_deck_status(ctx, deck_id, "generating")
    run_id = ctx.runs.create(deck_id, "generate", estimate=estimate, params={"document_id": doc_id})
    _update(ctx, doc_id, run_id=run_id)
    ctx.worker.submit(run_id, lambda: run_generation(ctx, doc_id, run_id, {"document_id": doc_id}))
    return doc_id, run_id


def register_resumers(ctx: AppContext) -> None:
    def resumer(run_id: str) -> Any:
        run = ctx.runs.get(run_id)
        doc_id = str(run.params["document_id"])
        set_deck_status(ctx, run.deck_id, "generating")
        return lambda: run_generation(ctx, doc_id, run_id, None)

    ctx.worker.register_resumer("generate", resumer)
