"""Parse a book PDF into pages with page labels and its table of contents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class Page:
    index: int  # 0-based physical index
    label: str  # printed label when present, else physical number (1-based)
    label_kind: str  # "printed" | "physical"
    text: str


@dataclass(frozen=True)
class TocEntry:
    level: int
    title: str
    page_index: int  # 0-based


def parse_book(path: Path) -> tuple[list[Page], list[TocEntry]]:
    with pymupdf.open(path) as doc:
        pages: list[Page] = []
        for page in doc:
            label = page.get_label() or ""
            kind = "printed" if label else "physical"
            pages.append(
                Page(
                    index=page.number or 0,
                    label=label or str((page.number or 0) + 1),
                    label_kind=kind,
                    text=str(page.get_text("text")),
                )
            )
        toc = [
            TocEntry(level=int(lvl), title=str(title).strip(), page_index=max(int(pno) - 1, 0))
            for lvl, title, pno, *_ in doc.get_toc(simple=True)
        ]
    return pages, toc
