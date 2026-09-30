"""Run bookkeeping shared by all pipeline stages: create, progress, finish, and events."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from slidex.api.schemas import Problem
from slidex.api.schemas import Run as RunOut
from slidex.core.errors import SlidexError
from slidex.db.base import Database, utcnow
from slidex.db.tables import CostEntry, Run
from slidex.graph.events import Broadcaster, DeckEvent


def run_out(db: Database, run: Run) -> RunOut:
    with db.session() as s:
        rows = s.execute(
            select(CostEntry.stage, func.sum(CostEntry.usd))
            .where(CostEntry.run_id == run.id)
            .group_by(CostEntry.stage)
        ).all()
    by_stage = {stage: round(float(usd or 0.0), 6) for stage, usd in rows}
    return RunOut(
        id=run.id,
        deck_id=run.deck_id,
        kind=run.kind,  # type: ignore[arg-type]
        status=run.status,  # type: ignore[arg-type]
        stage=run.stage,
        progress=run.progress,
        estimate=run.estimate,  # type: ignore[arg-type]
        cost_usd=round(sum(by_stage.values()), 6),
        cost_by_stage=by_stage,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error=Problem.model_validate(run.error) if run.error else None,
    )


class RunTracker:
    """Writes run state to the DB and mirrors each change as a deck event."""

    def __init__(self, db: Database, events: Broadcaster) -> None:
        self.db = db
        self.events = events

    def create(
        self,
        deck_id: str,
        kind: str,
        *,
        estimate: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        with self.db.session() as s:
            run = Run(deck_id=deck_id, kind=kind, estimate=estimate, params=params or {})
            s.add(run)
            s.flush()
            run_id = run.id
        self._emit(run_id, "run.started")
        return run_id

    def get(self, run_id: str) -> Run:
        with self.db.session() as s:
            run = s.get(Run, run_id)
            if run is None:
                raise SlidexError("not_found", f"Run {run_id} not found")
            return run

    def stage(self, run_id: str, stage: str, progress: float | None = None) -> None:
        with self.db.session() as s:
            run = s.get(Run, run_id)
            if run is None:
                return
            run.stage = stage
            run.status = "running"
            if progress is not None:
                run.progress = max(0.0, min(1.0, progress))
        self._emit(run_id, "run.stage")

    def progress(self, run_id: str, progress: float) -> None:
        with self.db.session() as s:
            run = s.get(Run, run_id)
            if run is None:
                return
            run.progress = max(0.0, min(1.0, progress))
        self._emit(run_id, "run.progress")

    def finish(
        self, run_id: str, status: str, error: SlidexError | None = None
    ) -> None:
        with self.db.session() as s:
            run = s.get(Run, run_id)
            if run is None:
                return
            run.status = status
            if status == "completed":
                run.progress = 1.0
            run.ended_at = utcnow() if status in ("completed", "failed", "cancelled") else None
            run.error = error.to_problem() if error else None
        event = {
            "completed": "run.completed",
            "failed": "run.failed",
            "paused": "run.paused",
            "cancelled": "run.failed",
        }.get(status, "run.stage")
        self._emit(run_id, event, message=error.detail if error else None)

    def _emit(self, run_id: str, event: str, message: str | None = None) -> None:
        run = self.get(run_id)
        payload = run_out(self.db, run).model_dump(mode="json")
        self.events.publish(
            DeckEvent(event=event, deck_id=run.deck_id, run=payload, message=message)
        )
