"""Fetcher: robots, size cap, timeout, per-host throttle, HTML/PDF extraction, paywalls (T049)."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator, Iterator

import httpx
import pymupdf
import pytest
import respx

from slidex.research import fetch
from slidex.research.fetch import FetchBlocked, Fetcher

ARTICLE = """<html><head><title>Quorum systems</title></head><body>
<nav>Home | About | Login</nav>
<article><h1>Quorum systems</h1>
<p>{body}</p>
<h2>Overlap</h2><p>Every read set intersects every write set, so a read sees the latest write.</p>
</article><footer>Copyright footer text</footer></body></html>"""
BODY = "A quorum system requires read and write sets of replicas to overlap. " * 12


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 0))]
    )


@pytest.fixture
def no_wait(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """Record throttle sleeps instead of actually sleeping."""
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def _sleep(delay: float, *a: object, **k: object) -> None:
        sleeps.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(fetch.asyncio, "sleep", _sleep)
    yield sleeps


@pytest.fixture
async def fetcher() -> AsyncIterator[Fetcher]:
    f = Fetcher()
    yield f
    await f.aclose()


@pytest.fixture
def web(_no_real_network: respx.MockRouter) -> respx.MockRouter:
    r = _no_real_network
    r.get("https://docs.example.org/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
    )
    r.get("https://docs.example.org/quorum").mock(
        return_value=httpx.Response(200, html=ARTICLE.format(body=BODY))
    )
    return r


def _pdf_bytes(pages: int = 3) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Chapter text on page {i + 1} about replication")
    doc.set_metadata({"title": "Open Textbook"})
    data: bytes = doc.tobytes()
    doc.close()
    return data


async def test_robots_disallow_blocks(
    web: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    with pytest.raises(FetchBlocked, match="robots"):
        await fetcher.fetch("https://docs.example.org/private/notes")


async def test_robots_missing_allows_everything(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    r = _no_real_network
    r.get("https://open.example.edu/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://open.example.edu/notes").mock(
        return_value=httpx.Response(200, html=ARTICLE.format(body=BODY))
    )
    assert await fetcher.robots_allows("https://open.example.edu/notes")
    page = await fetcher.fetch("https://open.example.edu/notes")
    assert page.status == 200


async def test_robots_fetched_once_per_host(
    web: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    await fetcher.fetch("https://docs.example.org/quorum")
    await fetcher.fetch("https://docs.example.org/quorum?utm_source=x")
    robots = [c for c in web.calls if c.request.url.path == "/robots.txt"]
    assert len(robots) == 1


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.8", "192.168.1.1", "::1"])
async def test_private_addresses_refused(
    monkeypatch: pytest.MonkeyPatch, fetcher: Fetcher, ip: str
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (ip, 0))])
    with pytest.raises(FetchBlocked, match="private"):
        await fetcher.fetch("https://intranet.example.com/")


async def test_non_http_refused(fetcher: Fetcher) -> None:
    with pytest.raises(FetchBlocked):
        await fetcher.fetch("ftp://files.example.com/book.pdf")


async def test_size_cap(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    r = _no_real_network
    r.get("https://big.example.org/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://big.example.org/huge").mock(
        return_value=httpx.Response(200, content=b"x" * (fetch.MAX_BYTES + 1))
    )
    with pytest.raises(FetchBlocked, match="5 MB"):
        await fetcher.fetch("https://big.example.org/huge")


def test_timeout_and_user_agent() -> None:
    f = Fetcher()
    assert f._client.timeout.read == fetch.TIMEOUT == 20.0
    assert f._client.headers["user-agent"] == fetch.USER_AGENT


async def test_one_request_per_second_per_host(
    web: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    await fetcher.fetch("https://docs.example.org/quorum")
    # robots.txt + page on one host → the page request waits for the 1 s interval
    assert no_wait and all(0 < s <= fetch.MIN_INTERVAL for s in no_wait)


async def test_different_hosts_not_throttled(fetcher: Fetcher, no_wait: list[float]) -> None:
    await fetcher._throttle("a.example.org")
    await fetcher._throttle("b.example.org")
    assert no_wait == []


async def test_html_main_text_extracted(
    web: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    page = await fetcher.fetch("https://docs.example.org/quorum")
    assert not page.is_pdf and not page.paywalled
    assert page.title == "Quorum systems"
    assert "read set intersects every write set" in page.text
    assert "Copyright footer" not in page.text and "Login" not in page.text


async def test_pdf_text_extracted(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    r = _no_real_network
    r.get("https://open.example.edu/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://open.example.edu/book.pdf").mock(
        return_value=httpx.Response(
            200, content=_pdf_bytes(), headers={"content-type": "application/pdf"}
        )
    )
    page = await fetcher.fetch("https://open.example.edu/book.pdf")
    assert page.is_pdf and page.page_count == 3
    assert page.title == "Open Textbook"
    assert "page 2 about replication" in page.text


async def test_paywall_markers_detected(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    r = _no_real_network
    r.get("https://journal.example.com/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://journal.example.com/article").mock(
        return_value=httpx.Response(
            200,
            html="<html><body><article><h1>Paper</h1><p>Abstract only.</p>"
            "<p>Subscribe to continue reading this article.</p></article></body></html>",
        )
    )
    page = await fetcher.fetch("https://journal.example.com/article")
    assert page.paywalled


@pytest.mark.parametrize("status", [401, 402, 403])
async def test_auth_status_is_paywall(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float], status: int
) -> None:
    r = _no_real_network
    r.get("https://journal.example.com/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://journal.example.com/locked").mock(return_value=httpx.Response(status))
    page = await fetcher.fetch("https://journal.example.com/locked")
    assert page.paywalled and page.text == ""


async def test_http_error_blocks(
    _no_real_network: respx.MockRouter, fetcher: Fetcher, no_wait: list[float]
) -> None:
    r = _no_real_network
    r.get("https://gone.example.com/robots.txt").mock(return_value=httpx.Response(404))
    r.get("https://gone.example.com/page").mock(return_value=httpx.Response(404))
    with pytest.raises(FetchBlocked, match="HTTP 404"):
        await fetcher.fetch("https://gone.example.com/page")


async def test_demo_web_serves_offline_pages(
    monkeypatch: pytest.MonkeyPatch, no_wait: list[float]
) -> None:
    from slidex.core import config

    monkeypatch.setenv("SLIDEX_DEMO_WEB", "1")
    config.get_settings.cache_clear()

    def _no_dns(*a: object, **k: object) -> None:
        raise AssertionError("demo pages must not need DNS")

    monkeypatch.setattr(socket, "getaddrinfo", _no_dns)
    f = Fetcher()
    try:
        page = await f.fetch("https://notes.example.edu/replication")
        assert "replication lag" in page.text
        locked = await f.fetch("https://paywall.example.com/article")
        assert locked.paywalled
    finally:
        await f.aclose()


async def test_demo_web_never_active_in_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from slidex.core import config

    monkeypatch.setenv("SLIDEX_DEMO_WEB", "1")
    monkeypatch.setenv("SLIDEX_FAKE_LLM", "0")
    config.get_settings.cache_clear()
    f = Fetcher()
    try:
        assert f._offline_hosts == frozenset()
    finally:
        await f.aclose()
