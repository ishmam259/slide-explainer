"""FetchCache: a ready source is reused for 30 days, then fetched again (T049)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from slidex.api.deps import AppContext
from slidex.db.tables import FetchCache, Source
from slidex.research import agent


class _CountingFetcher:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url: str) -> object:
        self.calls += 1
        raise agent.FetchBlocked("offline in this test")


def _ready_source(ctx: AppContext, url: str, fetched_days_ago: float | None) -> str:
    with ctx.db.session() as s:
        src = Source(
            kind="article",
            origin="web",
            title="t",
            url=url,
            url_normalized=url,
            access="usable",
            processing_status="ready",
        )
        s.add(src)
        if fetched_days_ago is not None:
            s.add(
                FetchCache(
                    url_normalized=url,
                    status=200,
                    fetched_at=datetime.now(UTC) - timedelta(days=fetched_days_ago),
                )
            )
        s.flush()
        return src.id


async def test_fresh_fetch_is_reused(app_ctx: AppContext) -> None:
    url = "https://docs.example.org/fresh"
    sid = _ready_source(app_ctx, url, fetched_days_ago=3)
    fetcher = _CountingFetcher()
    assert await agent.ingest_page(app_ctx, fetcher, sid, url, None)  # type: ignore[arg-type]
    assert fetcher.calls == 0


async def test_stale_fetch_is_refetched(app_ctx: AppContext) -> None:
    url = "https://docs.example.org/stale"
    sid = _ready_source(app_ctx, url, fetched_days_ago=31)
    fetcher = _CountingFetcher()
    assert not await agent.ingest_page(app_ctx, fetcher, sid, url, None)  # type: ignore[arg-type]
    assert fetcher.calls == 1
