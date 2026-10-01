"""Pass A: per-slide structured extraction (vision role). Spec FR-003–FR-006."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from sqlalchemy import delete, select

from slidex.api.deps import AppContext
from slidex.db.tables import Deck, Slide, Visual
from slidex.llm.client import ImageInput
from slidex.llm.prompts import load
from slidex.llm.schemas import SlideExtraction

PROMPT = "slide_extract.v1"
LOCAL_OCR_SKIP_CONFIDENCE = 0.9

Progress = Callable[[int, int], None]


def slide_input(deck: Deck, slide: Slide) -> str:
    parts = [f"Deck: {deck.title}", f"Slide {slide.number} of {deck.slide_count}"]
    ctx = deck.context or {}
    if ctx.get("course") or ctx.get("topic"):
        parts.append(f"Course context: {ctx.get('course', '')} {ctx.get('topic', '')}".strip())
    parts.append("Machine-extracted slide text:\n" + (slide.native_text.strip() or "(none)"))
    if slide.ocr_text:
        parts.append("OCR text (may contain errors):\n" + slide.ocr_text.strip())
    if slide.native_tables:
        parts.append(f"Tables (cells): {slide.native_tables}")
    parts.append("Speaker notes:\n" + (slide.notes.strip() or "(none)"))
    return "\n\n".join(parts)


async def extract_slide(ctx: AppContext, deck: Deck, slide: Slide, run_id: str | None) -> None:
    text_only = (
        slide.ocr_path == "local_ocr"
        and (slide.ocr_confidence or 0.0) >= LOCAL_OCR_SKIP_CONFIDENCE
        and "$" not in (slide.ocr_text or "")
    )
    images: list[ImageInput] = []
    if not text_only:
        data = ctx.files.read(slide.image_hash)
        images.append(ImageInput(data=data, sha256=slide.image_hash, detail="high"))
    result = await ctx.llm.parse(
        role="bulk" if text_only else "vision",
        stage="slide_extraction",
        prompt_version=PROMPT,
        instructions=load(PROMPT),
        input_text=slide_input(deck, slide),
        schema=SlideExtraction,
        images=images,
        run_id=run_id,
    )
    with ctx.db.session() as s:
        row = s.get(Slide, slide.id)
        assert row is not None
        row.extraction = result.model_dump(mode="json")
        row.clarity = result.clarity
        if not text_only and row.ocr_path != "native":
            row.ocr_path = "provider_vision"
        s.execute(delete(Visual).where(Visual.slide_id == slide.id))
        for v in result.visuals:
            s.add(
                Visual(
                    origin="slide",
                    slide_id=slide.id,
                    kind=v.kind,
                    description=v.description,
                    conveys=v.conveys,
                    explanation=v.description,
                    unreadable_parts=v.unreadable_parts,
                    image_hash=slide.image_hash,
                    caption=v.id,
                )
            )


async def extract_slides(
    ctx: AppContext, deck_id: str, run_id: str | None, on_progress: Progress | None = None
) -> None:
    """Extract every slide that has no extraction yet (idempotent; cache makes reruns free)."""
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        assert deck is not None
        todo = list(
            s.scalars(
                select(Slide)
                .where(Slide.deck_id == deck_id, Slide.extraction.is_(None))
                .order_by(Slide.number)
            )
        )
        total = deck.slide_count
    done = total - len(todo)

    async def one(slide: Slide) -> None:
        nonlocal done
        await extract_slide(ctx, deck, slide, run_id)
        done += 1
        if on_progress:
            on_progress(done, total)

    await asyncio.gather(*(one(sl) for sl in todo))
