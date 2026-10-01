"""Generate and validate the explanation for one slide (strong role)."""

from __future__ import annotations

from dataclasses import dataclass

from slidex.api.deps import AppContext
from slidex.db.tables import Slide
from slidex.explain.evidence import EvidencePack, gather
from slidex.explain.planner import SlidePlan
from slidex.explain.validate import strip_filler, validate_blocks
from slidex.llm.prompts import load
from slidex.llm.schemas import Block, EvidenceRef, ReferBackBlock, SlideExplanation

PROMPT = "slide_explain.v1"


@dataclass
class SlideResult:
    number: int
    title: str
    blocks: list[Block]
    evidence: dict[str, EvidenceRef]
    dropped: int
    reconstructed: bool


def _prompt_input(slide: Slide, plan: SlidePlan, pack: EvidencePack, retry_note: str = "") -> str:
    ex = slide.extraction or {}
    vague = slide.clarity in ("vague", "unreadable")
    lines = [f"SLIDE {slide.number}" + (" — VAGUE" if vague else "")]
    if vague and slide.interpretation:
        lines.append(
            f"Interpretation (confidence {slide.interpretation.get('confidence')}): "
            f"{slide.interpretation.get('meaning')}"
        )
    visuals = ex.get("visuals", [])
    if visuals:
        lines.append("Visuals on the slide (use these visual ids):")
        lines += [f"- {v.get('id')}: {v.get('kind')} — {v.get('description')}" for v in visuals]
    if ex.get("formulas"):
        lines.append("Formulas: " + "; ".join(f.get("latex", "") for f in ex["formulas"]))
    if plan.explain_fully:
        lines.append("EXPLAIN FULLY: " + ", ".join(plan.explain_fully))
    if plan.refer_back:
        lines.append(
            "REFER BACK (do not re-explain): "
            + ", ".join(f"{c} → slide {n}" for c, n in plan.refer_back.items())
        )
    lines.append("\nEVIDENCE:\n" + "\n\n".join(pack.prompt_parts))
    if retry_note:
        lines.append("\nFIX: " + retry_note)
    return "\n".join(lines)


async def explain_slide(
    ctx: AppContext,
    deck_id: str,
    slide: Slide,
    plan: SlidePlan,
    source_ids: list[str],
    unusable_ids: set[str],
    run_id: str | None,
) -> SlideResult:
    ex = slide.extraction or {}
    query = " ".join(
        [
            ex.get("topic") or "",
            *(ex.get("concepts") or []),
            (slide.interpretation or {}).get("meaning", ""),
        ]
    )
    pack = await gather(
        ctx, deck_id, slide, source_ids, run_id, query_text=query or ex.get("text", "")
    )
    vague = slide.clarity in ("vague", "unreadable")

    async def generate(note: str = "") -> SlideExplanation:
        return await ctx.llm.parse(
            role="strong",
            stage="explanation",
            prompt_version=PROMPT,
            instructions=load(PROMPT),
            input_text=_prompt_input(slide, plan, pack, note),
            schema=SlideExplanation,
            run_id=run_id,
        )

    result = await generate()
    check = validate_blocks(
        result.blocks,
        known_evidence=pack.ids(),
        unusable_evidence=unusable_ids,
        slide_is_vague=vague,
        first_pass=True,
    )
    kept = list(check.kept)
    dropped = len(check.dropped)
    if check.retry:
        bad = sorted(
            {c for b in check.retry for c in getattr(b, "citations", []) if c not in pack.ids()}
        )
        retried = await generate(
            f"Some blocks cited ids that do not exist ({', '.join(bad)}). "
            f"Cite only: {', '.join(sorted(pack.ids()))}."
        )
        second = validate_blocks(
            retried.blocks,
            known_evidence=pack.ids(),
            unusable_evidence=unusable_ids,
            slide_is_vague=vague,
            first_pass=False,
        )
        kept = second.kept  # use the corrected generation as a whole
        dropped = len(second.dropped)
        check = second
    if check.filler:
        filler_blocks = {id(b) for b, _ in check.filler}
        for b in kept:
            if id(b) in filler_blocks:
                for attr in ("markdown", "text", "steps_markdown"):
                    if isinstance(getattr(b, attr, None), str):
                        setattr(b, attr, strip_filler(getattr(b, attr)))
    for concept, n in plan.refer_back.items():
        if not any(isinstance(b, ReferBackBlock) and b.concept == concept for b in kept):
            kept.append(ReferBackBlock(concept=concept, slide=n))
    title = result.title or ex.get("title") or f"Slide {slide.number}"
    return SlideResult(
        slide.number, title, kept, pack.refs, dropped, any(b.type == "reconstructed" for b in kept)
    )
