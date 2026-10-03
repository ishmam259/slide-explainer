"""DB rows → API schemas."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from slidex.api import schemas as S
from slidex.api.deps import AppContext
from slidex.db import tables as T
from slidex.graph.runs import run_out


def file_url(digest: str | None) -> str:
    return f"/api/files/{digest}" if digest else ""


def deck_summary(d: T.Deck) -> S.DeckSummary:
    return S.DeckSummary(
        id=d.id,
        title=d.title,
        file_kind=d.file_kind,
        slide_count=d.slide_count,
        status=d.status,
        created_at=d.created_at,
    )


def deck_detail(ctx: AppContext, d: T.Deck) -> S.DeckDetail:
    with ctx.db.session() as s:
        counts = dict(
            s.execute(
                select(T.Slide.clarity, func.count())
                .where(T.Slide.deck_id == d.id)
                .group_by(T.Slide.clarity)
            ).all()
        )
        needs = (
            s.scalar(
                select(func.count())
                .select_from(T.Slide)
                .where(T.Slide.deck_id == d.id, T.Slide.needs_input.is_(True))
            )
            or 0
        )
        active = s.scalars(
            select(T.Run)
            .where(T.Run.deck_id == d.id, T.Run.status.in_(("running", "paused")))
            .order_by(T.Run.started_at.desc())
        ).first()
        cost = s.scalar(
            select(func.coalesce(func.sum(T.CostEntry.usd), 0.0))
            .join(T.Run, T.Run.id == T.CostEntry.run_id)
            .where(T.Run.deck_id == d.id)
        )
    base = deck_summary(d).model_dump()
    return S.DeckDetail(
        **base,
        context=S.DeckContext.model_validate(d.context or {}),
        clarity_counts=S.ClarityCounts(**{k: v for k, v in counts.items() if k != "pending"}),
        needs_input_count=needs,
        active_run=run_out(ctx.db, active) if active else None,
        cost_usd=round(float(cost or 0.0), 6),
        error=S.Problem.model_validate(d.error) if d.error else None,
    )


def slide_out(sl: T.Slide, visuals: list[T.Visual]) -> S.Slide:
    ex: dict[str, Any] = sl.extraction or {}
    interp = sl.interpretation
    return S.Slide(
        number=sl.number,
        image_url=file_url(sl.image_hash),
        title=ex.get("title"),
        text=ex.get("text") or sl.native_text,
        notes=sl.notes,
        formulas=[S.FormulaOut(**f) for f in ex.get("formulas", [])],
        visuals=[
            S.Visual(
                id=v.id,
                origin="slide",
                kind=v.kind,
                image_url=file_url(v.image_hash),
                caption=v.caption,
                description=v.description,
                explanation=v.conveys or v.explanation,
                unreadable_parts=v.unreadable_parts,
            )
            for v in visuals
        ],
        topic=ex.get("topic"),
        concepts=ex.get("concepts", []),
        clarity=sl.clarity,
        interpretation=S.Interpretation(
            meaning=interp["meaning"],
            confidence=interp["confidence"],
            rationale=interp.get("rationale", ""),
        )
        if interp
        else None,
        needs_input=sl.needs_input,
        learner_hint=sl.learner_hint,
        unreadable_regions=ex.get("unreadable_regions", []),
        ocr_path=sl.ocr_path,
    )


def topic_out(t: T.Topic) -> S.Topic:
    return S.Topic(
        id=t.id, name=t.name, slide_numbers=t.slide_numbers, research_status=t.research_status
    )


def source_out(x: T.Source) -> S.Source:
    return S.Source(
        id=x.id,
        kind=x.kind,
        origin=x.origin,
        title=x.title,
        authors=x.authors,
        publisher=x.publisher,
        year=x.year,
        url=x.url,
        isbn=x.isbn,
        access=x.access,
        blocked_reason=x.blocked_reason,
        processing_status=x.processing_status,
        page_count=x.page_count,
    )


def deck_source_out(ds: T.DeckSource, src: T.Source) -> S.DeckSource:
    return S.DeckSource(
        source=source_out(src),
        topic_ids=ds.topic_ids,
        relevance=ds.relevance,
        authority=ds.authority,
        reason=ds.reason,
        added_by=ds.added_by,
        approved=ds.approved,
    )


def evidence(e: dict[str, Any]) -> S.EvidenceRef:
    return S.EvidenceRef(
        kind=e.get("kind", "slide"),
        label=e.get("label", ""),
        slide=e.get("slide"),
        source_id=e.get("source_id"),
        page_label=e.get("page_label"),
        section_id=e.get("section_id"),
        url=e.get("url"),
    )


def document_out(ctx: AppContext, doc: T.ExplanationDocument) -> S.ExplanationDocument:
    cost = 0.0
    if doc.run_id:
        with ctx.db.session() as s:
            cost = float(
                s.scalar(
                    select(func.coalesce(func.sum(T.CostEntry.usd), 0.0)).where(
                        T.CostEntry.run_id == doc.run_id
                    )
                )
                or 0.0
            )
    return S.ExplanationDocument(
        id=doc.id,
        deck_id=doc.deck_id,
        organization=doc.organization,
        formats=doc.formats,
        slide_range=doc.slide_range,
        status=doc.status,
        progress=doc.progress,
        downloads={f: f"/api/documents/{doc.id}/download/{f}" for f in doc.files},
        stats=S.DocStats(
            **{k: v for k, v in (doc.stats or {}).items() if k in S.DocStats.model_fields}
        ),
        cost_usd=round(cost, 6),
        created_at=doc.created_at,
        error=S.Problem.model_validate(doc.error) if doc.error else None,
    )


def qa_turn_out(t: T.QaTurn) -> S.QaTurn:
    return S.QaTurn(
        id=t.id,
        thread_id=t.thread_id,
        role=t.role,
        text=t.text,
        citations=[evidence(c) for c in t.citations],
        declined=t.declined,
        created_at=t.created_at,
    )
