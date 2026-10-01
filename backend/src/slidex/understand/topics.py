"""Consolidate slide topics into ≤ max_topics research topics (bulk role)."""

from __future__ import annotations

from sqlalchemy import delete, select

from slidex.api.deps import AppContext
from slidex.db.tables import Deck, Slide, Topic
from slidex.llm.prompts import load
from slidex.llm.schemas import TopicConsolidation

PROMPT = "topics_consolidate.v1"


def build_input(deck: Deck, slides: list[Slide]) -> str:
    lines = [f"Deck: {deck.title}", f"Context: {deck.context or {}}", "Slides:"]
    for sl in slides:
        if sl.clarity == "divider":
            continue
        ex = sl.extraction or {}
        meaning = (sl.interpretation or {}).get("meaning")
        lines.append(
            f"- {sl.number}: topic={ex.get('topic', '?')}; concepts={ex.get('concepts', [])}"
            + (f"; meaning={meaning[:300]}" if meaning else "")
        )
    return "\n".join(lines)


async def consolidate_topics(ctx: AppContext, deck_id: str, run_id: str | None) -> int:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        assert deck is not None
        slides = list(
            s.scalars(select(Slide).where(Slide.deck_id == deck_id).order_by(Slide.number))
        )
    result = await ctx.llm.parse(
        role="bulk",
        stage="slide_extraction",
        prompt_version=PROMPT,
        instructions=load(PROMPT),
        input_text=build_input(deck, slides),
        schema=TopicConsolidation,
        run_id=run_id,
    )
    valid_numbers = {sl.number for sl in slides}
    seen: set[str] = set()
    with ctx.db.session() as s:
        s.execute(delete(Topic).where(Topic.deck_id == deck_id))
        for item in result.topics[: ctx.settings.max_topics]:
            key = item.name.strip().lower()
            numbers = sorted({n for n in item.slide_numbers if n in valid_numbers})
            if not key or key in seen or not numbers:
                continue
            seen.add(key)
            s.add(
                Topic(deck_id=deck_id, name=item.name.strip(), name_key=key, slide_numbers=numbers)
            )
    return len(seen)
