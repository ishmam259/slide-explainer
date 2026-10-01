"""Evidence gathering for one slide: the slide itself, retrieved passages, figures, disagreements.

Each item gets a short id used in prompts and citations: S<n> slide, B<k> book passage,
W<k> web section, F<k> book figure, D<k> disagreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.db.tables import Disagreement, Slide, Source, Visual
from slidex.llm.prompts import untrusted
from slidex.llm.schemas import EvidenceRef
from slidex.retrieval.embed import embed_query
from slidex.retrieval.index import Passage, collapsed_tree

K = 8
TOKEN_BUDGET = 3000


@dataclass
class EvidencePack:
    refs: dict[str, EvidenceRef] = field(default_factory=dict)
    prompt_parts: list[str] = field(default_factory=list)

    def ids(self) -> set[str]:
        return set(self.refs)


def slide_ref(number: int) -> EvidenceRef:
    return EvidenceRef(
        kind="slide", label=f"Slide {number}", slide=number, evidence_id=f"S{number}"
    )


def _source_label(src: Source) -> str:
    authors = ", ".join(src.authors[:2]) if src.authors else ""
    return f"{authors + ', ' if authors else ''}{src.title}"


def passage_ref(eid: str, p: Passage, src: Source) -> EvidenceRef:
    if p.owner_type == "book_node":
        pages = p.page_start if p.page_start == p.page_end else f"{p.page_start}–{p.page_end}"
        return EvidenceRef(
            kind="book",
            label=f"{_source_label(src)}, p. {pages}",
            evidence_id=eid,
            source_id=src.id,
            page_label=p.page_start,
        )
    label = f"{src.title} › {p.heading_path}" if p.heading_path else src.title
    url = f"{src.url}#{p.anchor}" if src.url and p.anchor else src.url
    return EvidenceRef(
        kind="web", label=label, evidence_id=eid, source_id=src.id, section_id=p.owner_id, url=url
    )


async def gather(
    ctx: AppContext,
    deck_id: str,
    slide: Slide,
    source_ids: list[str],
    run_id: str | None,
    *,
    query_text: str,
) -> EvidencePack:
    pack = EvidencePack()
    ex = slide.extraction or {}
    sid = f"S{slide.number}"
    pack.refs[sid] = slide_ref(slide.number)
    pack.prompt_parts.append(
        f"[{sid}] Slide {slide.number} text: {ex.get('text') or slide.native_text}\n"
        f"Speaker notes: {slide.notes or '(none)'}"
    )
    if source_ids:
        query = await embed_query(ctx, query_text, run_id, "explanation")
        passages = collapsed_tree(
            ctx.db, source_ids, np.asarray(query), k=K, token_budget=TOKEN_BUDGET
        )
        with ctx.db.session() as s:
            sources = {x.id: x for x in s.scalars(select(Source).where(Source.id.in_(source_ids)))}
        b = w = 0
        for p in passages:
            src = sources[p.source_id]
            if p.owner_type == "book_node":
                b += 1
                eid = f"B{b}"
            else:
                w += 1
                eid = f"W{w}"
            ref = passage_ref(eid, p, src)
            pack.refs[eid] = ref
            pack.prompt_parts.append(f"[{eid}] ({ref.label})\n{untrusted(src.id, p.text)}")
        with ctx.db.session() as s:
            figures = list(
                s.scalars(
                    select(Visual)
                    .where(
                        Visual.origin == "book",
                        Visual.source_id.in_(source_ids),
                        Visual.decorative.is_(False),
                    )
                    .limit(3)
                )
            )
        for i, f in enumerate(figures, start=1):
            eid = f"F{i}"
            fig_src = sources.get(f.source_id or "")
            book = _source_label(fig_src) if fig_src else "Book"
            label = f"{book}, p. {f.page_label}, {f.caption or 'figure'}"
            pack.refs[eid] = EvidenceRef(
                kind="book",
                label=label,
                evidence_id=eid,
                source_id=f.source_id,
                page_label=f.page_label,
            )
            pack.prompt_parts.append(f"[{eid}] Book figure (visual id {f.id}): {f.explanation}")
    with ctx.db.session() as s:
        disagreements = [
            d
            for d in s.scalars(select(Disagreement).where(Disagreement.deck_id == deck_id))
            if d.involves_slide == slide.number
        ]
    for i, d in enumerate(disagreements, start=1):
        eid = f"D{i}"
        pack.refs[eid] = EvidenceRef(
            kind="slide", label=f"Disagreement: {d.claim[:80]}", evidence_id=eid, slide=slide.number
        )
        pos = "; ".join(
            f"{p['statement']} ({', '.join(e['label'] for e in p['evidence'])})"
            for p in d.positions
        )
        pack.prompt_parts.append(
            f"[{eid}] Disagreement id {d.id}: {d.claim}. Positions: {pos}. "
            f"Assessment: {d.assessment}"
        )
    return pack
