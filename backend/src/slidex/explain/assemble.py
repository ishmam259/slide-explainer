"""Assemble per-slide results into the canonical ExplanationDocumentModel."""

from __future__ import annotations

from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.db.tables import DeckSource, Source
from slidex.explain.planner import DocumentPlan
from slidex.explain.slide import SlideResult
from slidex.llm.schemas import DocSection, ExplanationDocumentModel, SourceRef


def _source_ref(src: Source) -> SourceRef:
    return SourceRef(
        source_id=src.id,
        title=src.title,
        authors=src.authors,
        kind=src.kind,
        url=src.url,
        publisher=src.publisher,
        year=src.year,
    )


def assemble(
    ctx: AppContext,
    deck_id: str,
    title: str,
    organization: str,
    plan: DocumentPlan,
    results: dict[int, SlideResult],
    slide_images: dict[int, str],
) -> ExplanationDocumentModel:
    sections: list[DocSection] = []
    cited_sources: set[str] = set()
    for section_title, numbers in plan.sections:
        if organization == "by_topic":
            # One section per slide inside the topic keeps evidence ids unambiguous.
            for n in numbers:
                r = results.get(n)
                if r is None:
                    continue
                sections.append(
                    DocSection(
                        slide_numbers=[n],
                        title=f"{section_title} — Slide {n}: {r.title}",
                        slide_image_hash=slide_images.get(n),
                        blocks=r.blocks,
                        evidence=r.evidence,
                    )
                )
        else:
            n = numbers[0]
            r = results.get(n)
            if r is None:
                continue
            sections.append(
                DocSection(
                    slide_numbers=[n],
                    title=f"Slide {n}: {r.title}",
                    slide_image_hash=slide_images.get(n),
                    blocks=r.blocks,
                    evidence=r.evidence,
                )
            )
    for r in results.values():
        for b in r.blocks:
            for c in getattr(b, "citations", []):
                ref = r.evidence.get(c)
                if ref and ref.source_id:
                    cited_sources.add(ref.source_id)
    with ctx.db.session() as s:
        used = [
            _source_ref(x) for x in s.scalars(select(Source).where(Source.id.in_(cited_sources)))
        ]
        further = [
            _source_ref(x)
            for x in s.scalars(
                select(Source)
                .join(DeckSource, DeckSource.source_id == Source.id)
                .where(DeckSource.deck_id == deck_id, Source.access == "further_reading")
            )
        ]
    return ExplanationDocumentModel(
        title=title,
        organization=organization,
        sections=sections,
        sources=used,
        further_reading=further,
    )
