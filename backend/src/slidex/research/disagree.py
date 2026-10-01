"""Detect disagreements between sources, and between sources and slides (FR-016)."""

from __future__ import annotations

import numpy as np
from sqlalchemy import delete, select

from slidex.api.deps import AppContext
from slidex.db.tables import DeckSource, Disagreement, Slide, Source, Topic, WebSection
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import DisagreementFinding
from slidex.retrieval.embed import embed_query
from slidex.retrieval.index import search

PROMPT = "disagree.v1"
SECTIONS_PER_SOURCE = 2


async def detect_disagreements(ctx: AppContext, deck_id: str, run_id: str | None) -> int:
    with ctx.db.session() as s:
        s.execute(delete(Disagreement).where(Disagreement.deck_id == deck_id))
        topics = list(s.scalars(select(Topic).where(Topic.deck_id == deck_id)))
        slides = {sl.number: sl for sl in s.scalars(select(Slide).where(Slide.deck_id == deck_id))}
        links = list(
            s.execute(
                select(DeckSource.source_id, DeckSource.topic_ids)
                .join(Source, Source.id == DeckSource.source_id)
                .where(DeckSource.deck_id == deck_id, Source.access == "usable")
            ).all()
        )
    found = 0
    for topic in topics:
        source_ids = [sid for sid, tids in links if topic.id in tids]
        if len(source_ids) < 2:
            continue
        evidence: dict[str, dict[str, object]] = {}
        parts: list[str] = []
        for n in topic.slide_numbers:
            sl = slides.get(n)
            if sl is None:
                continue
            eid = f"S{n}"
            evidence[eid] = {"kind": "slide", "slide": n, "label": f"Slide {n}"}
            parts.append(f"[{eid}] Slide {n}: {(sl.extraction or {}).get('text', sl.native_text)}")
        query = await embed_query(ctx, topic.name, run_id, "research_fetch_rank")
        k = 0
        with ctx.db.session() as s:
            for sid in source_ids:
                sec_ids = list(s.scalars(select(WebSection.id).where(WebSection.source_id == sid)))
                for hit in search(
                    ctx.db, "web_section", sec_ids, np.asarray(query), SECTIONS_PER_SOURCE
                ):
                    sec = s.get(WebSection, hit.owner_id)
                    src = s.get(Source, sid)
                    assert sec is not None and src is not None
                    k += 1
                    eid = f"W{k}"
                    evidence[eid] = {
                        "kind": "web",
                        "source_id": sid,
                        "section_id": sec.id,
                        "url": src.url,
                        "label": f"{src.title} › {sec.heading_path}".strip(" ›"),
                    }
                    parts.append(f"[{eid}] {untrusted(sid, sec.text)}")
        result = await ctx.llm.parse(
            role="strong",
            stage="research_fetch_rank",
            prompt_version=PROMPT,
            instructions=load(PROMPT),
            input_text=f"Topic: {topic.name}\n\n" + "\n\n".join(parts),
            schema=DisagreementFinding,
            run_id=run_id,
        )
        with ctx.db.session() as s:
            for d in result.disagreements:
                positions = [
                    {
                        "statement": p.statement,
                        "evidence": [evidence[e] for e in p.evidence_ids if e in evidence],
                    }
                    for p in d.positions
                ]
                if sum(1 for p in positions if p["evidence"]) < 2:
                    continue  # constitution I: every position must be grounded
                s.add(
                    Disagreement(
                        deck_id=deck_id,
                        topic_id=topic.id,
                        claim=d.claim,
                        positions=positions,
                        involves_slide=d.involves_slide,
                        assessment=d.assessment,
                    )
                )
                found += 1
    return found
