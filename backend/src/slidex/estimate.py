"""Cost/time estimates shown before expensive steps (FR-009, research.md R10).

Deterministic token heuristics × model prices, scaled by a per-stage calibration factor
(EMA of actual/estimated) that improves as runs complete.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select

from slidex.api.deps import AppContext
from slidex.api.schemas import RunEstimate, RunEstimateBudget, StageEstimate
from slidex.core.hardware import detect_gpu
from slidex.core.pricing import Usage, cost_usd
from slidex.db.tables import Calibration, CostEntry, Deck, DeckSource, Run, Slide, Source, Topic

PAGE_TOKENS = 550
SECTION_TOKENS = 1800  # average cleaned web page


def _ratio(ctx: AppContext, stage: str) -> float:
    with ctx.db.session() as s:
        row = s.get(Calibration, stage)
        return row.ratio_ema if row else 1.0


def _stage(
    ctx: AppContext,
    stage: str,
    role: str,
    calls: int,
    tin: int,
    tout: int,
    tool_calls: int = 0,
    path: Literal["provider", "local"] = "provider",
) -> StageEstimate:
    model = ctx.llm.roles[role].model
    usd = cost_usd(
        model,
        Usage(input_tokens=tin, output_tokens=tout, tool_calls=tool_calls),
        web_search_fee=ctx.settings.web_search_fee_usd,
    ) * _ratio(ctx, stage)
    return StageEstimate(
        stage=stage,
        model=model,
        calls=calls,
        input_tokens=tin,
        output_tokens=tout,
        tool_calls=tool_calls,
        usd=round(usd, 4),
        path=path,
    )


def estimate(
    ctx: AppContext, deck_id: str, stage: str, formats: list[str] | None = None
) -> RunEstimate:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        if deck is None:
            from slidex.core.errors import SlidexError

            raise SlidexError("not_found", f"Deck {deck_id} not found")
        n_topics = (
            s.scalar(select(func.count()).select_from(Topic).where(Topic.deck_id == deck_id)) or 0
        )
        n_slides = deck.slide_count
        n_vague = (
            s.scalar(
                select(func.count())
                .select_from(Slide)
                .where(Slide.deck_id == deck_id, Slide.clarity.in_(("vague", "unreadable")))
            )
            or 0
        )
        book_pages = (
            s.scalar(
                select(func.coalesce(func.sum(Source.page_count), 0))
                .join(DeckSource, DeckSource.source_id == Source.id)
                .where(
                    DeckSource.deck_id == deck_id,
                    DeckSource.approved.is_(True),
                    Source.kind == "book",
                    Source.access == "usable",
                    Source.processing_status != "ready",
                )
            )
            or 0
        )
    st = ctx.settings
    stages: list[StageEstimate] = []
    if stage == "research":
        topics = min(n_topics or 1, st.max_topics)
        pages = topics * st.pages_per_topic
        searches = topics * st.searches_per_topic * 2
        stages += [
            _stage(
                ctx,
                "research_search",
                "search",
                searches,
                searches * 1500,
                searches * 600,
                tool_calls=searches,
            ),
            _stage(
                ctx, "research_fetch_rank", "bulk", pages * 2, pages * 2 * 2500, pages * 2 * 120
            ),
            _stage(ctx, "disagreements", "strong", topics, topics * 5000, topics * 1500),
        ]
        minutes = 1 + topics * 0.8
    elif stage == "process_sources":
        leaves = book_pages * PAGE_TOKENS // 350
        clusters = max(leaves // 6, 1) if book_pages else 0
        stages.append(
            _stage(ctx, "book_processing", "bulk", clusters, clusters * 2400, clusters * 500)
        )
        minutes = 0.5 + book_pages / 120
    elif stage == "generate":
        n = max(n_slides, 1)
        stages.append(
            _stage(
                ctx,
                "explanation",
                "strong",
                n + n_vague // 2,
                (n + n_vague // 2) * 5500,
                (n + n_vague // 2) * 2500,
            )
        )
        minutes = 1 + n * 0.15
    else:  # extract
        gpu = detect_gpu().available
        stages.append(
            _stage(
                ctx,
                "slide_extraction",
                "vision",
                n_slides,
                n_slides * 1800,
                n_slides * 700,
                path="local" if gpu else "provider",
            )
        )
        stages.append(
            _stage(ctx, "interpretation", "strong", n_vague, n_vague * 2500, n_vague * 600)
        )
        minutes = 0.5 + n_slides * 0.05
    total = round(sum(x.usd for x in stages), 4)
    budget = RunEstimateBudget(
        topics=min(n_topics, st.max_topics),
        searches_per_topic=st.searches_per_topic,
        pages_per_topic=st.pages_per_topic,
    )
    return RunEstimate(stages=stages, total_usd=total, est_minutes=round(minutes, 1), budget=budget)


def calibrate(ctx: AppContext, run_id: str, alpha: float = 0.3) -> None:
    """After a run completes, move each stage's ratio toward actual / estimated."""
    with ctx.db.session() as s:
        run = s.get(Run, run_id)
        if run is None or not run.estimate:
            return
        actual = dict(
            s.execute(
                select(CostEntry.stage, func.sum(CostEntry.usd))
                .where(CostEntry.run_id == run_id)
                .group_by(CostEntry.stage)
            ).all()
        )
        for st in run.estimate.get("stages", []):
            est = float(st.get("usd") or 0.0)
            act = float(actual.get(st["stage"]) or 0.0)
            if est <= 0 or act <= 0:
                continue
            row = s.get(Calibration, st["stage"]) or Calibration(
                stage=st["stage"], ratio_ema=1.0, samples=0
            )
            row.ratio_ema = (1 - alpha) * row.ratio_ema + alpha * (act / est)
            row.samples += 1
            s.merge(row)
