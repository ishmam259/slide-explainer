"""Untrusted-content classifier: injection / spam / paywall pages are excluded (FR-017)."""

from __future__ import annotations

import re

from slidex.api.deps import AppContext
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import SafetyVerdict

PROMPT = "safety.v1"
MAX_CHARS = 8000

# Cheap deterministic pre-filter; the model classifier catches subtler cases.
_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) instructions"
    r"|disregard (the |all )?(previous|prior) instructions"
    r"|you are now (an?|the) |system prompt|as an ai (language )?model,? you must)",
    re.IGNORECASE,
)


def quick_injection_check(text: str) -> bool:
    return bool(_INJECTION.search(text))


async def classify(
    ctx: AppContext, source_id: str, title: str, text: str, run_id: str | None
) -> SafetyVerdict:
    if quick_injection_check(text):
        return SafetyVerdict(
            verdict="injection", reason="Contains instructions aimed at AI agents."
        )
    return await ctx.llm.parse(
        role="bulk",
        stage="research_fetch_rank",
        prompt_version=PROMPT,
        instructions=load(PROMPT),
        input_text=f"Title: {title}\n\n" + untrusted(source_id, text[:MAX_CHARS]),
        schema=SafetyVerdict,
        run_id=run_id,
    )
