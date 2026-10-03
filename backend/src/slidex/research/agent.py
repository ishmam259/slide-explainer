"""Research agent: per topic plan → search → fetch → safety → section/embed → rank.

Bounded by the research budget (searches/pages per topic). Every step is idempotent:
sources are de-duplicated by normalized URL and model calls are cached, so a resumed run
does not pay twice (FR-030).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import delete, select

from slidex.api.deps import AppContext
from slidex.db.tables import Deck, DeckSource, Slide, Source, Topic, WebSection
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import QueryPlan, SourceRanking
from slidex.research.fetch import FetchBlocked, Fetcher, FetchResult, normalize_url
from slidex.research.safety import classify
from slidex.research.sections import split_sections
from slidex.retrieval.embed import embed_owners

log = logging.getLogger(__name__)

OPEN_DOMAINS = (
    "openstax.org",
    "libretexts.org",
    "open.umn.edu",
    "ocw.mit.edu",
    "arxiv.org",
    "wikipedia.org",
    "pressbooks.pub",
)
BOOK_MIN_PAGES = 80
KEEP_PER_TOPIC = 5
MIN_RELEVANCE = 0.4

Progress = Callable[[int, int], None]


@dataclass
class TopicView:
    id: str
    name: str
    slide_numbers: list[int]
    slides_text: str


def _topic_views(ctx: AppContext, deck_id: str, topic_ids: list[str] | None) -> list[TopicView]:
    with ctx.db.session() as s:
        q = select(Topic).where(Topic.deck_id == deck_id)
        if topic_ids:
            q = q.where(Topic.id.in_(topic_ids))
        topics = list(s.scalars(q))
        slides = {sl.number: sl for sl in s.scalars(select(Slide).where(Slide.deck_id == deck_id))}
    views = []
    for t in topics:
        text = []
        for n in t.slide_numbers:
            sl = slides.get(n)
            if sl is None:
                continue
            meaning = (sl.interpretation or {}).get("meaning")
            text.append(f"Slide {n}: {meaning or (sl.extraction or {}).get('text', '')}"[:500])
        views.append(TopicView(t.id, t.name, t.slide_numbers, "\n".join(text)))
    return views


async def plan_queries(
    ctx: AppContext, deck: Deck, topic: TopicView, run_id: str | None
) -> list[str]:
    plan = await ctx.llm.parse(
        role="bulk",
        stage="research_search",
        prompt_version="plan_queries.v1",
        instructions=load("plan_queries.v1"),
        input_text=(
            f"Topic: {topic.name}\nCourse context: {deck.context or {}}\n"
            f"What the slides say:\n{topic.slides_text}"
        ),
        schema=QueryPlan,
        run_id=run_id,
    )
    return plan.queries[: ctx.settings.searches_per_topic]


async def discover(
    ctx: AppContext, deck: Deck, topic: TopicView, run_id: str | None
) -> list[tuple[str, str]]:
    """Return up to pages_per_topic (url, title) candidates; open domains first."""
    queries = await plan_queries(ctx, deck, topic, run_id)
    limit = ctx.settings.pages_per_topic
    seen: dict[str, str] = {}
    instructions = load("search.v1")
    for domains in (OPEN_DOMAINS, None):
        for q in queries:
            if len(seen) >= limit:
                break
            result = await ctx.llm.search(
                q,
                instructions=instructions,
                stage="research_search",
                allowed_domains=domains,
                run_id=run_id,
            )
            for c in result.citations:
                key = normalize_url(c.url)
                if key not in seen and len(seen) < limit:
                    seen[key] = c.title
        if len(seen) >= limit // 2:
            break
    with ctx.db.session() as s:
        t = s.get(Topic, topic.id)
        if t is not None:
            t.queries = queries
    return list(seen.items())


def _upsert_source(ctx: AppContext, url: str, title: str) -> str:
    with ctx.db.session() as s:
        src = s.scalars(select(Source).where(Source.url_normalized == url)).one_or_none()
        if src is None:
            src = Source(
                kind="other", origin="web", title=title or url, url=url, url_normalized=url
            )
            s.add(src)
            s.flush()
        return src.id


async def ingest_page(
    ctx: AppContext, fetcher: Fetcher, source_id: str, url: str, run_id: str | None
) -> bool:
    """Fetch + classify + section + embed one page. Returns True if usable."""
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None
        if src.processing_status == "ready":
            return src.access == "usable"
        src.processing_status = "fetching"
    try:
        page: FetchResult = await fetcher.fetch(url)
    except (FetchBlocked, httpx.HTTPError) as exc:
        reason = exc.reason if isinstance(exc, FetchBlocked) else f"fetch failed: {exc!r}"[:300]
        _set_access(ctx, source_id, "blocked", reason, "failed")
        return False
    if page.paywalled:
        _set_access(ctx, source_id, "further_reading", "paywalled or login required", "ready")
        return False
    if page.is_pdf and (page.page_count or 0) >= BOOK_MIN_PAGES:
        digest = ctx.files.put_bytes(page.raw, "pdf")
        with ctx.db.session() as s:
            src = s.get(Source, source_id)
            assert src is not None
            src.kind = "book"
            src.file_hash = digest
            src.page_count = page.page_count
            src.title = page.title or src.title
            src.processing_status = "pending"  # processed by the books pipeline after approval
        verdict = await classify(ctx, source_id, page.title or url, page.text[:8000], run_id)
        if verdict.verdict != "ok":
            _set_access(ctx, source_id, "blocked", f"{verdict.verdict}: {verdict.reason}", "failed")
            return False
        return True
    if len(page.text.strip()) < 200:
        _set_access(ctx, source_id, "blocked", "no readable main content", "failed")
        return False
    verdict = await classify(ctx, source_id, page.title or url, page.text, run_id)
    if verdict.verdict == "paywall":
        _set_access(ctx, source_id, "further_reading", verdict.reason, "ready")
        return False
    if verdict.verdict != "ok":
        _set_access(ctx, source_id, "blocked", f"{verdict.verdict}: {verdict.reason}", "failed")
        return False
    sections = split_sections(page.text)
    with ctx.db.session() as s:
        s.execute(delete(WebSection).where(WebSection.source_id == source_id))
        rows = [
            WebSection(
                source_id=source_id,
                heading_path=sec.heading_path,
                anchor=sec.anchor,
                text=sec.text,
                order=i,
            )
            for i, sec in enumerate(sections)
        ]
        s.add_all(rows)
        s.flush()
        items = [(r.id, f"{r.heading_path}\n{r.text}") for r in rows]
        src = s.get(Source, source_id)
        assert src is not None
        src.title = page.title or src.title
        src.access = "usable"
        src.processing_status = "processing"
    await embed_owners(ctx, "web_section", items, stage="research_fetch_rank", run_id=run_id)
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None
        src.processing_status = "ready"
    return True


def _set_access(ctx: AppContext, source_id: str, access: str, reason: str, status: str) -> None:
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        if src is not None:
            src.access = access
            src.blocked_reason = reason[:500]
            src.processing_status = status


def _source_preview(ctx: AppContext, source_id: str, chars: int = 4000) -> tuple[str, str]:
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None
        texts = list(
            s.scalars(
                select(WebSection.text)
                .where(WebSection.source_id == source_id)
                .order_by(WebSection.order)
            )
        )
    body = "\n\n".join(texts)[:chars] if texts else f"(book PDF, {src.page_count} pages)"
    return src.title, body


async def rank_source(
    ctx: AppContext, deck_id: str, topic: TopicView, source_id: str, run_id: str | None
) -> SourceRanking:
    title, body = _source_preview(ctx, source_id)
    with ctx.db.session() as s:
        url = s.get(Source, source_id).url  # type: ignore[union-attr]
    return await ctx.llm.parse(
        role="bulk",
        stage="research_fetch_rank",
        prompt_version="rank.v1",
        instructions=load("rank.v1"),
        input_text=(
            f"Topic: {topic.name}\nSlides {topic.slide_numbers}:\n{topic.slides_text}\n\n"
            f"Source title: {title}\nURL: {url}\n" + untrusted(source_id, body)
        ),
        schema=SourceRanking,
        run_id=run_id,
    )


async def research_topic(
    ctx: AppContext, fetcher: Fetcher, deck: Deck, topic: TopicView, run_id: str | None
) -> None:
    with ctx.db.session() as s:
        t = s.get(Topic, topic.id)
        assert t is not None
        t.research_status = "searching"
    candidates = await discover(ctx, deck, topic, run_id)
    usable: list[str] = []
    seen_ids: list[str] = []
    for url, title in candidates:
        source_id = _upsert_source(ctx, url, title)
        seen_ids.append(source_id)
        if await ingest_page(ctx, fetcher, source_id, url, run_id):
            usable.append(source_id)
    _link_further_reading(ctx, deck.id, topic.id, seen_ids)
    ranked: list[tuple[float, str, SourceRanking]] = []
    for source_id in usable:
        r = await rank_source(ctx, deck.id, topic, source_id, run_id)
        if r.relevance >= MIN_RELEVANCE:
            ranked.append((0.6 * r.relevance + 0.4 * r.authority, source_id, r))
    ranked.sort(key=lambda x: x[0], reverse=True)
    with ctx.db.session() as s:
        for _, source_id, r in ranked[:KEEP_PER_TOPIC]:
            src = s.get(Source, source_id)
            assert src is not None
            if src.kind == "other":
                src.kind = r.kind
            ds = s.get(DeckSource, (deck.id, source_id))
            if ds is None:
                ds = DeckSource(
                    deck_id=deck.id,
                    source_id=source_id,
                    topic_ids=[],
                    added_by="research",
                    relevance=0.0,
                    authority=0.0,
                    approved=True,
                    reason="",
                )
                s.add(ds)
            ds.topic_ids = sorted({*ds.topic_ids, topic.id})
            ds.relevance = max(ds.relevance, r.relevance)
            ds.authority = max(ds.authority, r.authority)
            ds.reason = r.reason[:200]
        t = s.get(Topic, topic.id)
        assert t is not None
        t.research_status = "done" if ranked else "no_reliable_source"


def _link_further_reading(
    ctx: AppContext, deck_id: str, topic_id: str, source_ids: list[str]
) -> None:
    """Paywalled/non-free sources are listed as further reading only (FR-011); never approved."""
    with ctx.db.session() as s:
        for source_id in source_ids:
            src = s.get(Source, source_id)
            if src is None or src.access != "further_reading":
                continue
            ds = s.get(DeckSource, (deck_id, source_id))
            if ds is None:
                s.add(
                    DeckSource(
                        deck_id=deck_id,
                        source_id=source_id,
                        topic_ids=[topic_id],
                        added_by="research",
                        relevance=0.0,
                        authority=0.0,
                        approved=False,
                        reason="Not freely available — further reading",
                    )
                )


async def research_deck(
    ctx: AppContext,
    deck_id: str,
    run_id: str | None,
    topic_ids: list[str] | None = None,
    on_progress: Progress | None = None,
    fetcher: Fetcher | None = None,
) -> None:
    with ctx.db.session() as s:
        deck = s.get(Deck, deck_id)
        assert deck is not None
    topics = _topic_views(ctx, deck_id, topic_ids)
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    done = 0
    try:
        sem = asyncio.Semaphore(3)

        async def one(t: TopicView) -> None:
            nonlocal done
            async with sem:
                await research_topic(ctx, fetcher, deck, t, run_id)
            done += 1
            if on_progress:
                on_progress(done, len(topics))

        await asyncio.gather(*(one(t) for t in topics))
    finally:
        if own:
            await fetcher.aclose()
