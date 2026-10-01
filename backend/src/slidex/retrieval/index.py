"""Exact cosine search over stored embeddings (research.md R8) + collapsed-tree retrieval."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select

from slidex.db.base import Database
from slidex.db.tables import BookNode, DeckSource, Embedding, Source, WebSection
from slidex.retrieval.embed import from_blob
from slidex.retrieval.tokens import count_tokens


@dataclass(frozen=True)
class Hit:
    owner_type: str
    owner_id: str
    score: float


def cosine_top_k(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    if matrix.size == 0:
        return []
    q = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    scores = (matrix @ q) / norms
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order]


def search(
    db: Database, owner_type: str, owner_ids: list[str], query: np.ndarray, k: int
) -> list[Hit]:
    if not owner_ids:
        return []
    with db.session() as s:
        rows = s.execute(
            select(Embedding.owner_id, Embedding.vector).where(
                Embedding.owner_type == owner_type, Embedding.owner_id.in_(owner_ids)
            )
        ).all()
    if not rows:
        return []
    matrix = np.vstack([from_blob(v) for _, v in rows])
    return [Hit(owner_type, rows[i][0], score) for i, score in cosine_top_k(query, matrix, k)]


@dataclass(frozen=True)
class Passage:
    owner_type: str  # "book_node" | "web_section"
    owner_id: str
    source_id: str
    text: str
    score: float
    page_start: str | None = None
    page_end: str | None = None
    heading_path: str | None = None
    anchor: str | None = None


def approved_usable_sources(db: Database, deck_id: str) -> list[str]:
    with db.session() as s:
        return list(
            s.scalars(
                select(Source.id)
                .join(DeckSource, DeckSource.source_id == Source.id)
                .where(
                    DeckSource.deck_id == deck_id,
                    DeckSource.approved.is_(True),
                    Source.access == "usable",
                )
            )
        )


def collapsed_tree(
    db: Database,
    source_ids: list[str],
    query: np.ndarray,
    *,
    k: int = 8,
    token_budget: int = 3000,
) -> list[Passage]:
    """RAPTOR 'collapsed tree': rank book nodes of every level + web sections together."""
    if not source_ids:
        return []
    with db.session() as s:
        nodes = {
            n.id: n for n in s.scalars(select(BookNode).where(BookNode.source_id.in_(source_ids)))
        }
        sections = {
            w.id: w
            for w in s.scalars(select(WebSection).where(WebSection.source_id.in_(source_ids)))
        }
    hits = search(db, "book_node", list(nodes), query, k * 3) + search(
        db, "web_section", list(sections), query, k * 3
    )
    hits.sort(key=lambda h: h.score, reverse=True)
    out: list[Passage] = []
    used = 0
    for h in hits:
        if len(out) >= k:
            break
        if h.owner_type == "book_node":
            n = nodes[h.owner_id]
            p = Passage("book_node", n.id, n.source_id, n.text, h.score, n.page_start, n.page_end)
        else:
            w = sections[h.owner_id]
            p = Passage(
                "web_section",
                w.id,
                w.source_id,
                w.text,
                h.score,
                heading_path=w.heading_path,
                anchor=w.anchor,
            )
        t = count_tokens(p.text)
        if used + t > token_budget and out:
            continue
        out.append(p)
        used += t
    return out
