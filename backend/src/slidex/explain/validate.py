"""Citation integrity + filler lint for generated blocks (constitution I & II, FR-020–FR-024)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from slidex.llm.schemas import Block, ReconstructedBlock, ReferBackBlock

FILLER_PATTERNS = [
    r"\bin this (slide|section|chapter),? we (will|are going to)\b",
    r"\blet'?s dive (in|into)\b",
    r"\bas we can see\b",
    r"\bit is important to note that\b",
    r"\bin conclusion,",
    r"\bwithout further ado\b",
    r"\bgreat question\b",
    r"\bto sum (it )?up\b",
]
_FILLER = re.compile("|".join(FILLER_PATTERNS), re.IGNORECASE)


@dataclass
class ValidationResult:
    kept: list[Block] = field(default_factory=list)
    retry: list[Block] = field(default_factory=list)  # blocks with unknown evidence ids
    dropped: list[tuple[Block, str]] = field(default_factory=list)
    filler: list[tuple[Block, str]] = field(default_factory=list)


def block_text(block: Block) -> str:
    for attr in ("markdown", "text", "steps_markdown"):
        value = getattr(block, attr, None)
        if isinstance(value, str):
            return value
    return ""


def find_filler(text: str) -> list[str]:
    return [m.group(0) for m in _FILLER.finditer(text)]


def validate_blocks(
    blocks: list[Block],
    *,
    known_evidence: set[str],
    unusable_evidence: set[str],
    slide_is_vague: bool,
    first_pass: bool,
) -> ValidationResult:
    """Classify each block. On the first pass, unknown-citation blocks are returned for a retry;
    on the second pass they are dropped."""
    res = ValidationResult()
    for b in blocks:
        if isinstance(b, ReferBackBlock):
            res.kept.append(b)
            continue
        cites = list(getattr(b, "citations", []))
        if not cites:
            res.dropped.append((b, "no citations"))
            continue
        if any(c in unusable_evidence for c in cites):
            res.dropped.append((b, "cites a source that is not usable"))
            continue
        if any(c not in known_evidence for c in cites):
            if first_pass:
                res.retry.append(b)
            else:
                res.dropped.append((b, "cites unknown evidence"))
            continue
        if isinstance(b, ReconstructedBlock) and not slide_is_vague:
            res.dropped.append((b, "reconstruction is only allowed on vague slides"))
            continue
        filler = find_filler(block_text(b))
        if filler:
            res.filler.append((b, "; ".join(filler)))
        res.kept.append(b)
    return res


def strip_filler(text: str) -> str:
    """Remove sentences that contain a filler phrase."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(s for s in sentences if not _FILLER.search(s)).strip()
