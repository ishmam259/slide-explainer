"""Polite, safe fetching of public pages (constitution VIII, research.md R6).

robots.txt honoured, private/loopback addresses refused (SSRF guard), 1 request/s per host,
20 s timeout, 5 MB cap, HTML → main text (trafilatura, markdown), PDF → text (PyMuPDF).
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import pymupdf
import trafilatura

USER_AGENT = "SlideExplainer/0.1 (+local study tool)"
TIMEOUT = 20.0
MAX_BYTES = 5 * 1024 * 1024
MIN_INTERVAL = 1.0
_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|ref_src$)")
_PAYWALL = re.compile(
    r"(subscribe to (continue|read)|sign in to (continue|read)|log in to (continue|read)|"
    r"this content is for subscribers|purchase (this|the) (article|chapter)|"
    r"buy (this|the) (book|ebook|chapter)|paywall)",
    re.IGNORECASE,
)


class FetchBlocked(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content_type: str
    title: str | None
    text: str
    is_pdf: bool
    raw: bytes
    page_count: int | None = None
    paywalled: bool = False


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    path = parts.path or "/"
    return urlunsplit((scheme, host + port, path, query, ""))


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


async def assert_public(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchBlocked("only http(s) URLs are fetched")
    host = parts.hostname
    if not host:
        raise FetchBlocked("URL has no host")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as exc:
        raise FetchBlocked(f"host not found: {host}") from exc
    if not infos or not all(_is_public_ip(str(info[4][0])) for info in infos):
        raise FetchBlocked("private or local network address refused")


class Fetcher:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _throttle(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._last.get(host, 0.0) + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[host] = time.monotonic()

    async def robots_allows(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(base)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            try:
                await self._throttle(parts.netloc)
                resp = await self._client.get(f"{base}/robots.txt")
                if resp.status_code >= 400:
                    parser.parse([])
                else:
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                parser.parse([])
            self._robots[base] = parser
        return parser.can_fetch(USER_AGENT, url)

    async def fetch(self, url: str) -> FetchResult:
        url = normalize_url(url)
        await assert_public(url)
        if not await self.robots_allows(url):
            raise FetchBlocked("disallowed by robots.txt")
        host = urlsplit(url).netloc
        await self._throttle(host)
        async with self._client.stream("GET", url) as resp:
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FetchBlocked("page larger than 5 MB")
                chunks.append(chunk)
            raw = b"".join(chunks)
            status = resp.status_code
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            final_url = str(resp.url)
        if status in (401, 402, 403):
            return FetchResult(final_url, status, ctype, None, "", False, raw, paywalled=True)
        if status >= 400:
            raise FetchBlocked(f"HTTP {status}")
        await assert_public(final_url)  # redirects must stay public too
        if ctype == "application/pdf" or raw[:5] == b"%PDF-":
            return _pdf_result(final_url, status, raw)
        html = raw.decode(resp.encoding or "utf-8", errors="replace")
        text = (
            trafilatura.extract(
                html, output_format="markdown", include_tables=True, include_links=False
            )
            or ""
        )
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta and meta.title else None
        paywalled = bool(_PAYWALL.search(html[:200_000])) and len(text) < 2500
        return FetchResult(
            final_url, status, ctype or "text/html", title, text, False, raw, paywalled=paywalled
        )


def _pdf_result(url: str, status: int, raw: bytes) -> FetchResult:
    try:
        doc = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise FetchBlocked("PDF could not be read") from exc
    with doc:
        if doc.needs_pass:
            raise FetchBlocked("PDF is password protected")
        title = (doc.metadata or {}).get("title") or None
        text = "\n\n".join(str(page.get_text("text")) for page in doc.pages())
        pages = doc.page_count
    return FetchResult(url, status, "application/pdf", title, text, True, raw, page_count=pages)
