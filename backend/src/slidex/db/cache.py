"""SQLite-backed model-call cache and cost-ledger sink."""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.sqlite import insert

from slidex.core.pricing import LedgerEntry, Usage
from slidex.db.base import Database
from slidex.db.tables import CostEntry, ModelCallCache


class DbCallCache:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> Any | None:
        with self._db.session() as s:
            row = s.get(ModelCallCache, key)
            return row.output if row is not None else None

    def put(self, key: str, model: str, output: Any, usage: Usage) -> None:
        stmt = (
            insert(ModelCallCache)
            .values(
                key=key,
                model=model,
                output=output,
                usage={
                    "input_tokens": usage.input_tokens,
                    "cached_tokens": usage.cached_tokens,
                    "output_tokens": usage.output_tokens,
                    "tool_calls": usage.tool_calls,
                },
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        with self._db.session() as s:
            s.execute(stmt)


def cost_sink(db: Database) -> Any:
    def _sink(entry: LedgerEntry) -> None:
        with db.session() as s:
            s.add(
                CostEntry(
                    run_id=entry.run_id,
                    stage=entry.stage,
                    model=entry.model,
                    input_tokens=entry.usage.input_tokens,
                    cached_tokens=entry.usage.cached_tokens,
                    output_tokens=entry.usage.output_tokens,
                    tool_calls=entry.usage.tool_calls,
                    usd=entry.usd,
                    at=entry.at,
                )
            )

    return _sink
