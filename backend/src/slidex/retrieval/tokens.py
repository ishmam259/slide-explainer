"""Token counting (o200k_base, used by GPT-5.x models).

tiktoken downloads its encoding file on first use. To keep that off the request path, the app
warms it in a background thread at startup and caches it under the data dir. If it is not
available (offline, tests with SLIDEX_APPROX_TOKENS=1), counting falls back to ~4 chars/token.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

log = logging.getLogger(__name__)

_lock = threading.Lock()
_enc: object | None = None
_failed = False


def warm(cache_dir: Path) -> None:
    """Load (and if needed download) the encoding. Safe to call from a background thread."""
    global _enc, _failed
    if os.environ.get("SLIDEX_APPROX_TOKENS") == "1":
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache_dir))
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
    except Exception as exc:  # network or cache problems: approximate instead
        log.warning("tiktoken unavailable (%s); using approximate token counts", exc)
        with _lock:
            _failed = True
        return
    with _lock:
        _enc = enc


def _encoder() -> object | None:
    with _lock:
        return _enc


def count_tokens(text: str) -> int:
    enc = _encoder()
    if enc is None:
        return max(1, len(text) // 4) if text else 0
    return len(enc.encode(text, disallowed_special=()))  # type: ignore[attr-defined]


def truncate_tokens(text: str, limit: int) -> str:
    enc = _encoder()
    if enc is None:
        return text[: limit * 4]
    ids = enc.encode(text, disallowed_special=())  # type: ignore[attr-defined]
    return text if len(ids) <= limit else enc.decode(ids[:limit])  # type: ignore[attr-defined]
