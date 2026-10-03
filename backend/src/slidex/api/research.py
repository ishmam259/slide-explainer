"""Research & sources (US2): estimate, topics, confirm, source list, add/toggle, approve."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Literal

import pymupdf
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select

from slidex.api import convert
from slidex.api import schemas as S
from slidex.api.deps import AppContext, get_ctx
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, DeckSource, Disagreement, Source, Topic
from slidex.estimate import estimate
from slidex.graph import deck_graph
from slidex.graph.runs import run_out
from slidex.research.agent import ingest_page
from slidex.research.fetch import Fetcher, normalize_url

router = APIRouter(tags=["research"])
Ctx = Annotated[AppContext, Depends(get_ctx)]


@router.get("/decks/{deck_id}/estimate", operation_id="getEstimate")
def get_estimate(
    deck_id: str,
    ctx: Ctx,
    stage: Annotated[Literal["research", "process_sources", "generate"], Query()],
    formats: Annotated[str | None, Query(description="comma-separated")] = None,
) -> S.RunEstimate:
    return estimate(ctx, deck_id, stage, formats.split(",") if formats else None)


@router.get("/decks/{deck_id}/topics", operation_id="listTopics")
def list_topics(deck_id: str, ctx: Ctx) -> list[S.Topic]:
    with ctx.db.session() as s:
        return [
            convert.topic_out(t) for t in s.scalars(select(Topic).where(Topic.deck_id == deck_id))
        ]


@router.post("/decks/{deck_id}/research", operation_id="startResearch", status_code=202)
def start_research(deck_id: str, body: S.ResearchIn, ctx: Ctx) -> S.Run:
    est = estimate(ctx, deck_id, "research").model_dump(mode="json")
    run_id = deck_graph.confirm_research(ctx, deck_id, body.topic_ids, est)
    return run_out(ctx.db, ctx.runs.get(run_id))


@router.get("/decks/{deck_id}/sources", operation_id="listDeckSources")
def list_sources(deck_id: str, ctx: Ctx) -> S.SourceList:
    with ctx.db.session() as s:
        topics = list(s.scalars(select(Topic).where(Topic.deck_id == deck_id)))
        rows = list(
            s.execute(
                select(DeckSource, Source)
                .join(Source, Source.id == DeckSource.source_id)
                .where(DeckSource.deck_id == deck_id)
            ).all()
        )
    by_topic = []
    for t in topics:
        items = [
            convert.deck_source_out(ds, src)
            for ds, src in rows
            if t.id in ds.topic_ids and src.access == "usable"
        ]
        items.sort(key=lambda x: 0.6 * x.relevance + 0.4 * x.authority, reverse=True)
        by_topic.append(S.TopicSources(topic=convert.topic_out(t), sources=items))
    unassigned = [
        convert.deck_source_out(ds, src)
        for ds, src in rows
        if not ds.topic_ids and src.access == "usable"
    ]
    if unassigned:
        by_topic.append(
            S.TopicSources(
                topic=S.Topic(
                    id="learner", name="Added by you", slide_numbers=[], research_status="done"
                ),
                sources=unassigned,
            )
        )
    further = [convert.source_out(src) for _, src in rows if src.access == "further_reading"]
    return S.SourceList(by_topic=by_topic, further_reading=further)


@router.post("/decks/{deck_id}/sources", operation_id="addDeckSource", status_code=201)
async def add_source(
    deck_id: str,
    ctx: Ctx,
    file: Annotated[UploadFile | None, File()] = None,
    url: Annotated[str | None, Form()] = None,
    topic_ids: Annotated[str | None, Form(description="JSON list of topic ids")] = None,
) -> S.DeckSource:
    if (file is None) == (url is None):
        raise SlidexError("validation_error", "Provide either a PDF file or a URL.")
    tids: list[str] = json.loads(topic_ids) if topic_ids else []
    if file is not None:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise SlidexError("unsupported_file", "Books must be PDF files.")
        tmp = Path(tempfile.mkdtemp(prefix="slidex-book-"))
        try:
            dest = tmp / "book.pdf"
            with dest.open("wb") as out:
                shutil.copyfileobj(file.file, out)
            try:
                with pymupdf.open(dest) as doc:
                    pages = doc.page_count
                    title = (doc.metadata or {}).get("title") or Path(file.filename or "").stem
            except Exception as exc:
                raise SlidexError("corrupt_file", "The book PDF could not be read.") from exc
            digest = ctx.files.put_file(dest, "pdf")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        with ctx.db.session() as s:
            src = s.scalars(select(Source).where(Source.file_hash == digest)).first()
            if src is None:
                src = Source(
                    kind="book",
                    origin="learner_file",
                    title=title or "Book",
                    file_hash=digest,
                    page_count=pages,
                    access="usable",
                )
                s.add(src)
                s.flush()
            source_id = src.id
    else:
        assert url is not None
        norm = normalize_url(url)
        with ctx.db.session() as s:
            src = s.scalars(select(Source).where(Source.url_normalized == norm)).first()
            if src is None:
                src = Source(
                    kind="other", origin="learner_url", title=norm, url=norm, url_normalized=norm
                )
                s.add(src)
                s.flush()
            source_id = src.id

        async def _ingest() -> bool:
            fetcher = Fetcher()
            try:
                return await ingest_page(ctx, fetcher, source_id, norm, None)
            finally:
                await fetcher.aclose()

        await asyncio.to_thread(ctx.worker.run_sync, _ingest)
    with ctx.db.session() as s:
        ds = s.get(DeckSource, (deck_id, source_id))
        if ds is None:
            ds = DeckSource(
                deck_id=deck_id,
                source_id=source_id,
                topic_ids=tids,
                relevance=1.0,
                authority=1.0,
                reason="Added by you",
                added_by="learner",
                approved=True,
            )
            s.add(ds)
        src = s.get(Source, source_id)
        assert src is not None
        return convert.deck_source_out(ds, src)


@router.patch("/decks/{deck_id}/sources/{source_id}", operation_id="updateDeckSource")
def update_source(deck_id: str, source_id: str, body: S.SourceUpdate, ctx: Ctx) -> S.DeckSource:
    with ctx.db.session() as s:
        ds = s.get(DeckSource, (deck_id, source_id))
        src = s.get(Source, source_id)
        if ds is None or src is None:
            raise SlidexError("not_found", "Source not linked to this deck.")
        ds.approved = body.approved
        return convert.deck_source_out(ds, src)


@router.post("/decks/{deck_id}/sources/approve", operation_id="approveSources", status_code=202)
def approve(deck_id: str, ctx: Ctx) -> S.Run:
    est = estimate(ctx, deck_id, "process_sources").model_dump(mode="json")
    run_id = deck_graph.approve_sources(ctx, deck_id, est)
    return run_out(ctx.db, ctx.runs.get(run_id))


@router.get("/decks/{deck_id}/disagreements", operation_id="listDisagreements")
def list_disagreements(deck_id: str, ctx: Ctx) -> list[S.Disagreement]:
    with ctx.db.session() as s:
        if s.get(Deck, deck_id) is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        rows = list(s.scalars(select(Disagreement).where(Disagreement.deck_id == deck_id)))
    return [
        S.Disagreement(
            id=d.id,
            topic_id=d.topic_id,
            claim=d.claim,
            involves_slide=d.involves_slide,
            assessment=d.assessment,
            positions=[
                S.PositionOut(
                    statement=p["statement"], evidence=[convert.evidence(e) for e in p["evidence"]]
                )
                for p in d.positions
            ],
        )
        for d in rows
    ]
