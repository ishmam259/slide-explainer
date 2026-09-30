"""Model prices (USD per 1M tokens) and the per-run cost ledger."""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Price:
    input: float
    cached_input: float
    output: float


# Checked against developers.openai.com on 2026-09-30.
PRICES: dict[str, Price] = {
    "gpt-5.4-nano": Price(input=0.20, cached_input=0.02, output=1.25),
    "gpt-5.4-mini": Price(input=0.75, cached_input=0.075, output=4.50),
    "gpt-5.5": Price(input=5.00, cached_input=0.50, output=30.00),
    "text-embedding-3-small": Price(input=0.02, cached_input=0.02, output=0.0),
    "text-embedding-3-large": Price(input=0.13, cached_input=0.13, output=0.0),
}

_SNAPSHOT_SUFFIX_LEN = len("-2026-03-17")


def base_model(model: str) -> str:
    """Map a dated snapshot id (e.g. gpt-5.4-nano-2026-03-17) to its base id."""
    if model in PRICES:
        return model
    candidate = model[:-_SNAPSHOT_SUFFIX_LEN]
    if candidate in PRICES:
        return candidate
    raise KeyError(f"No price for model '{model}'")


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0


def cost_usd(model: str, usage: Usage, *, web_search_fee: float = 0.0) -> float:
    price = PRICES[base_model(model)]
    uncached = max(usage.input_tokens - usage.cached_tokens, 0)
    usd = (
        uncached * price.input
        + usage.cached_tokens * price.cached_input
        + usage.output_tokens * price.output
    ) / 1_000_000
    return round(usd + usage.tool_calls * web_search_fee, 8)


@dataclass(frozen=True)
class LedgerEntry:
    run_id: str | None
    stage: str
    model: str
    usage: Usage
    usd: float
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CostLedger:
    """Thread-safe record of model usage; an optional sink persists each entry."""

    def __init__(
        self, *, web_search_fee: float, sink: Callable[[LedgerEntry], None] | None = None
    ) -> None:
        self._fee = web_search_fee
        self._sink = sink
        self._lock = threading.Lock()
        self.entries: list[LedgerEntry] = []

    def record(self, run_id: str | None, stage: str, model: str, usage: Usage) -> LedgerEntry:
        entry = LedgerEntry(
            run_id=run_id,
            stage=stage,
            model=model,
            usage=usage,
            usd=cost_usd(model, usage, web_search_fee=self._fee),
        )
        with self._lock:
            self.entries.append(entry)
        if self._sink is not None:
            self._sink(entry)
        return entry

    def by_stage(self, run_id: str) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        with self._lock:
            for e in self.entries:
                if e.run_id == run_id:
                    totals[e.stage] += e.usd
        return dict(totals)

    def total(self, run_id: str) -> float:
        return sum(self.by_stage(run_id).values())
