"""Leaf passages of ~350 tokens on paragraph boundaries, tracking page labels."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slidex.books.parse import Page
from slidex.retrieval.tokens import count_tokens

TARGET_TOKENS = 350


@dataclass(frozen=True)
class Leaf:
    text: str
    page_start: int  # physical index
    page_end: int
    tokens: int


def chunk_pages(pages: list[Page], target: int = TARGET_TOKENS) -> list[Leaf]:
    leaves: list[Leaf] = []
    buf: list[str] = []
    buf_tokens = 0
    start = end = 0
    for page in pages:
        for para in (p.strip() for p in re.split(r"\n\s*\n", page.text)):
            if not para:
                continue
            para = re.sub(r"\s*\n\s*", " ", para)
            t = count_tokens(para)
            if buf and buf_tokens + t > target:
                leaves.append(Leaf(" \n".join(buf), start, end, buf_tokens))
                buf, buf_tokens = [], 0
            if not buf:
                start = page.index
            buf.append(para)
            buf_tokens += t
            end = page.index
    if buf:
        leaves.append(Leaf(" \n".join(buf), start, end, buf_tokens))
    return leaves
