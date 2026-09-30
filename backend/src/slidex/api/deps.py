"""Application context shared by routers and pipeline jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request

from slidex.core.config import Settings
from slidex.core.models import resolve_roles
from slidex.core.pricing import CostLedger
from slidex.db.base import Database
from slidex.db.cache import DbCallCache, cost_sink
from slidex.db.files import FileStore
from slidex.graph.events import Broadcaster
from slidex.graph.runs import RunTracker
from slidex.graph.worker import Worker
from slidex.llm.client import LLM, OpenAIClient
from slidex.llm.fake import FakeLLM

TESTS_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


@dataclass
class AppContext:
    settings: Settings
    db: Database
    files: FileStore
    ledger: CostLedger
    events: Broadcaster
    worker: Worker
    runs: RunTracker
    _llm: LLM | None = field(default=None, repr=False)

    @classmethod
    def build(cls, settings: Settings) -> AppContext:
        resolve_roles(settings)  # fail fast on disallowed models
        db = Database(settings.db_path)
        db.init()
        events = Broadcaster()
        return cls(
            settings=settings,
            db=db,
            files=FileStore(settings.files_path),
            ledger=CostLedger(web_search_fee=settings.web_search_fee_usd, sink=cost_sink(db)),
            events=events,
            worker=Worker(),
            runs=RunTracker(db, events),
        )

    @property
    def llm(self) -> LLM:
        """Created lazily so the app starts (and /health works) without an API key."""
        if self._llm is None:
            if self.settings.fake_llm:
                self._llm = FakeLLM(
                    self.settings,
                    ledger=self.ledger,
                    recordings_dir=TESTS_FIXTURES / "llm_recordings",
                    search_fixture=TESTS_FIXTURES / "web" / "search_results.json",
                )
            else:
                self._llm = OpenAIClient(
                    self.settings, cache=DbCallCache(self.db), ledger=self.ledger
                )
        return self._llm


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx
