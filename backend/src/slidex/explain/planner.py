"""Decide where each concept is explained in full (once) and where to refer back (FR-023)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

SYNONYM_SIMILARITY = 0.9


@dataclass(frozen=True)
class SlidePlanInput:
    number: int
    concepts: list[str]
    topic: str | None
    is_divider: bool = False


@dataclass
class SlidePlan:
    number: int
    explain_fully: list[str] = field(default_factory=list)
    refer_back: dict[str, int] = field(default_factory=dict)  # concept -> slide number


@dataclass
class DocumentPlan:
    order: list[int]  # slide numbers in output order
    sections: list[tuple[str, list[int]]]  # (section title, slide numbers)
    slides: dict[int, SlidePlan]


def _canonical(concepts: Sequence[str], vectors: dict[str, np.ndarray] | None) -> dict[str, str]:
    """Map each concept to a canonical representative (case-folded; merged synonyms)."""
    canon: dict[str, str] = {}
    reps: list[str] = []
    for c in concepts:
        key = c.strip().lower()
        if key in canon:
            continue
        match = next((r for r in reps if r == key), None)
        if match is None and vectors is not None and key in vectors:
            v = vectors[key]
            for r in reps:
                rv = vectors.get(r)
                if rv is None:
                    continue
                sim = float(v @ rv / ((np.linalg.norm(v) * np.linalg.norm(rv)) or 1.0))
                if sim >= SYNONYM_SIMILARITY:
                    match = r
                    break
        canon[key] = match or key
        if match is None:
            reps.append(key)
    return canon


def plan_document(
    slides: Sequence[SlidePlanInput],
    *,
    organization: str = "by_slide",
    slide_range: tuple[int, int] | None = None,
    concept_vectors: dict[str, np.ndarray] | None = None,
) -> DocumentPlan:
    chosen = [
        s
        for s in sorted(slides, key=lambda s: s.number)
        if slide_range is None or slide_range[0] <= s.number <= slide_range[1]
    ]
    if organization == "by_topic":
        groups: dict[str, list[int]] = {}
        for s in chosen:
            if s.is_divider:
                continue
            groups.setdefault((s.topic or "Other").strip(), []).append(s.number)
        sections = [(t, nums) for t, nums in groups.items()]
        order = [n for _, nums in sections for n in nums]
    else:
        order = [s.number for s in chosen if not s.is_divider]
        sections = [(f"Slide {n}", [n]) for n in order]

    all_concepts = [c for s in chosen for c in s.concepts]
    canon = _canonical(all_concepts, concept_vectors)
    by_number = {s.number: s for s in chosen}
    first_seen: dict[str, int] = {}
    plans: dict[int, SlidePlan] = {}
    for n in order:
        plan = SlidePlan(number=n)
        for c in by_number[n].concepts:
            key = canon.get(c.strip().lower(), c.strip().lower())
            if key in first_seen and first_seen[key] != n:
                plan.refer_back[c] = first_seen[key]
            elif c not in plan.explain_fully:
                first_seen.setdefault(key, n)
                plan.explain_fully.append(c)
        plans[n] = plan
    return DocumentPlan(order=order, sections=sections, slides=plans)
