"""Decks and slides (US1): upload, list, detail, update, delete, reorder, hints."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import delete, select

from slidex.api import convert
from slidex.api import schemas as S
from slidex.api.deps import AppContext, get_ctx
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, Slide, Visual
from slidex.graph import deck_graph
from slidex.intake.deck import create_deck
from slidex.understand.interpret import interpret_slide

router = APIRouter(tags=["decks"])
Ctx = Annotated[AppContext, Depends(get_ctx)]


def _deck(ctx: AppContext, deck_id: str) -> Deck:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        return deck


@router.get("/decks", operation_id="listDecks")
def list_decks(ctx: Ctx) -> list[S.DeckSummary]:
    with ctx.db.session() as s:
        return [
            convert.deck_summary(d)
            for d in s.scalars(select(Deck).order_by(Deck.created_at.desc()))
        ]


@router.post("/decks", operation_id="createDeck", status_code=201)
async def create(
    ctx: Ctx,
    files: Annotated[list[UploadFile], File(description="One PPTX or PDF, or 1–300 images")],
    context: Annotated[str | None, Form(description="JSON-encoded DeckContext")] = None,
) -> S.DeckDetail:
    try:
        deck_context = S.DeckContext.model_validate(json.loads(context) if context else {})
    except (json.JSONDecodeError, ValidationError) as exc:
        raise SlidexError("validation_error", f"Invalid context: {exc}") from exc
    tmp = Path(tempfile.mkdtemp(prefix="slidex-upload-"))
    try:
        saved: list[tuple[str, Path]] = []
        for i, f in enumerate(files):
            name = Path(f.filename or f"file{i}").name
            dest = tmp / f"{i:04d}{Path(name).suffix.lower()}"
            with dest.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved.append((name, dest))
        deck_id = await asyncio.to_thread(
            create_deck, ctx, saved, deck_context.model_dump(exclude_none=True)
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    deck_graph.start_extract(ctx, deck_id)
    return convert.deck_detail(ctx, _deck(ctx, deck_id))


@router.get("/decks/{deck_id}", operation_id="getDeck")
def get_deck(deck_id: str, ctx: Ctx) -> S.DeckDetail:
    return convert.deck_detail(ctx, _deck(ctx, deck_id))


@router.patch("/decks/{deck_id}", operation_id="updateDeck")
def update_deck(deck_id: str, body: S.DeckUpdate, ctx: Ctx) -> S.DeckDetail:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            raise SlidexError("not_found", f"Deck {deck_id} not found")
        if body.title is not None:
            deck.title = body.title
        if body.context is not None:
            deck.context = body.context.model_dump(exclude_none=True)
    return convert.deck_detail(ctx, _deck(ctx, deck_id))


@router.delete("/decks/{deck_id}", operation_id="deleteDeck", status_code=204)
def delete_deck(deck_id: str, ctx: Ctx) -> Response:
    with ctx.db.session() as s:
        s.execute(delete(Deck).where(Deck.id == deck_id))
    return Response(status_code=204)


@router.put("/decks/{deck_id}/order", operation_id="reorderImageSlides")
def reorder(deck_id: str, body: S.OrderIn, ctx: Ctx) -> S.DeckDetail:
    deck = _deck(ctx, deck_id)
    if deck.file_kind != "images" or deck.status not in (
        "ready_for_research",
        "awaiting_research_confirm",
    ):
        raise SlidexError("invalid_state", "Only image decks can be reordered, before research.")
    if sorted(body.order) != list(range(1, deck.slide_count + 1)):
        raise SlidexError("validation_error", "order must be a permutation of 1..slide_count")
    with ctx.db.session() as s:
        slides = {sl.number: sl for sl in s.scalars(select(Slide).where(Slide.deck_id == deck_id))}
        for sl in slides.values():
            sl.number = -sl.number  # avoid unique clashes while renumbering
        s.flush()
        for new, old in enumerate(body.order, start=1):
            slides[old].number = new
    return convert.deck_detail(ctx, deck)


@router.get("/decks/{deck_id}/slides", operation_id="listSlides")
def list_slides(deck_id: str, ctx: Ctx) -> list[S.Slide]:
    with ctx.db.session() as s:
        slides = list(
            s.scalars(select(Slide).where(Slide.deck_id == deck_id).order_by(Slide.number))
        )
        visuals: dict[str, list[Visual]] = {}
        for v in s.scalars(select(Visual).where(Visual.slide_id.in_([sl.id for sl in slides]))):
            visuals.setdefault(v.slide_id or "", []).append(v)
    return [convert.slide_out(sl, visuals.get(sl.id, [])) for sl in slides]


def _slide(ctx: AppContext, deck_id: str, number: int) -> S.Slide:
    with ctx.db.session() as s:
        sl = s.scalars(
            select(Slide).where(Slide.deck_id == deck_id, Slide.number == number)
        ).one_or_none()
        if sl is None:
            raise SlidexError("not_found", f"Slide {number} not found")
        visuals = list(s.scalars(select(Visual).where(Visual.slide_id == sl.id)))
    return convert.slide_out(sl, visuals)


@router.get("/decks/{deck_id}/slides/{number}", operation_id="getSlide")
def get_slide(deck_id: str, number: int, ctx: Ctx) -> S.Slide:
    return _slide(ctx, deck_id, number)


@router.put("/decks/{deck_id}/slides/{number}/hint", operation_id="setSlideHint")
async def set_hint(deck_id: str, number: int, body: S.HintIn, ctx: Ctx) -> S.Slide:
    with ctx.db.session() as s:
        sl = s.scalars(
            select(Slide).where(Slide.deck_id == deck_id, Slide.number == number)
        ).one_or_none()
        if sl is None:
            raise SlidexError("not_found", f"Slide {number} not found")
        if sl.clarity not in ("vague", "unreadable"):
            raise SlidexError("invalid_state", "Hints apply to vague or unreadable slides.")
        sl.learner_hint = body.hint
        sl.interpretation = None
    await asyncio.to_thread(
        ctx.worker.run_sync, lambda: interpret_slide(ctx, deck_id, number, None)
    )
    return _slide(ctx, deck_id, number)
