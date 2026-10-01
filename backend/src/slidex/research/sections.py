"""Split fetched page text into ≤ 400-token sections with heading paths (citation anchors)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slidex.retrieval.tokens import count_tokens

MAX_TOKENS = 400
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Section:
    heading_path: str
    anchor: str | None
    text: str


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def split_sections(text: str, max_tokens: int = MAX_TOKENS) -> list[Section]:
    stack: list[str] = []
    out: list[Section] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        path = " › ".join(stack)
        anchor = _slug(stack[-1]) if stack else None
        for piece in _pack(body, max_tokens):
            out.append(Section(heading_path=path, anchor=anchor, text=piece))

    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            del stack[level - 1 :]
            stack.append(m.group(2).strip())
        else:
            buf.append(line)
    flush()
    return out


def _pack(body: str, max_tokens: int) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for para in paras:
        t = count_tokens(para)
        if t > max_tokens:
            words = para.split()
            step = max(1, int(len(words) * max_tokens / t))
            for i in range(0, len(words), step):
                pieces.append(" ".join(words[i : i + step]))
            continue
        if cur and cur_tokens + t > max_tokens:
            pieces.append("\n\n".join(cur))
            cur, cur_tokens = [], 0
        cur.append(para)
        cur_tokens += t
    if cur:
        pieces.append("\n\n".join(cur))
    return pieces
