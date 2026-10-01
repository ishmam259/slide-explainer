"""Pass B: interpret vague/unreadable slides from their context (strong role). FR-007, FR-008."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.db.tables import Deck, Slide
from slidex.llm.prompts import load
from slidex.llm.schemas import SlideInterpretation

PROMPT = "slide_interpret.v1"
WINDOW = 3
NEEDS_INPUT_BELOW = 0.5
INTERPRETED = ("vague", "unreadable")


def needs_interpretation(slide: Slide) -> bool:
    return slide.clarity in INTERPRETED


def neighbour_numbers(number: int, total: int, window: int = WINDOW) -> list[int]:
    return [
        n for n in range(number - window, number + window + 1) if 1 <= n <= total and n != number
    ]


def _summary(slide: Slide) -> str:
    ex = slide.extraction or {}
    meaning = (slide.interpretation or {}).get("meaning")
    text = meaning or ex.get("text") or slide.native_text
    return f"Slide {slide.number} [{slide.clarity}] topic={ex.get('topic', '?')}: {text[:600]}"


def build_input(deck: Deck, slide: Slide, neighbours: list[Slide]) -> str:
    ctx = deck.context or {}
    ex = slide.extraction or {}
    lines = [
        f"Deck title: {deck.title}",
        f"Learner context: course={ctx.get('course') or '-'}, level={ctx.get('level') or '-'}, "
        f"topic={ctx.get('topic') or '-'}, notes={ctx.get('notes') or '-'}",
        f"TARGET slide {slide.number} ({slide.clarity}):",
        f"  text: {ex.get('text') or slide.native_text or '(none)'}",
        f"  visuals: {[v.get('description') for v in ex.get('visuals', [])]}",
        f"  unreadable: {ex.get('unreadable_regions', [])}",
        f"  speaker notes: {slide.notes or '(none)'}",
        f"  LEARNER HINT: {slide.learner_hint}" if slide.learner_hint else "  learner hint: (none)",
        "Neighbouring slides:",
        *[f"  {_summary(n)}" for n in neighbours],
    ]
    return "\n".join(lines)


async def interpret_slide(
    ctx: AppContext, deck_id: str, number: int, run_id: str | None
) -> SlideInterpretation | None:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        slide = s.scalars(
            select(Slide).where(Slide.deck_id == deck_id, Slide.number == number)
        ).one_or_none()
        if deck is None or slide is None or not needs_interpretation(slide):
            return None
        nums = neighbour_numbers(number, deck.slide_count)
        neighbours = list(
            s.scalars(
                select(Slide)
                .where(Slide.deck_id == deck_id, Slide.number.in_(nums))
                .order_by(Slide.number)
            )
        )
    result = await ctx.llm.parse(
        role="strong",
        stage="interpretation",
        prompt_version=PROMPT,
        instructions=load(PROMPT),
        input_text=build_input(deck, slide, neighbours),
        schema=SlideInterpretation,
        run_id=run_id,
    )
    if slide.learner_hint:
        result.used.hint = True
    with ctx.db.session() as s:
        row = s.get(Slide, slide.id)
        assert row is not None
        row.interpretation = result.model_dump(mode="json")
        row.needs_input = result.confidence < NEEDS_INPUT_BELOW
    return result


async def interpret_vague(ctx: AppContext, deck_id: str, run_id: str | None) -> int:
    """Interpret every vague/unreadable slide lacking an interpretation. Returns the count."""
    with ctx.db.session() as s:
        numbers = list(
            s.scalars(
                select(Slide.number).where(
                    Slide.deck_id == deck_id,
                    Slide.clarity.in_(INTERPRETED),
                    Slide.interpretation.is_(None),
                )
            )
        )
    await asyncio.gather(*(interpret_slide(ctx, deck_id, n, run_id) for n in numbers))
    return len(numbers)
