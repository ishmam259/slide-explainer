"""Embed owners (book nodes, web sections, slides, concepts) and store float32 vectors."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.db.tables import Embedding
from slidex.retrieval.tokens import truncate_tokens

MAX_EMBED_TOKENS = 8000


def to_blob(vec: Sequence[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


async def embed_owners(
    ctx: AppContext,
    owner_type: str,
    items: Sequence[tuple[str, str]],
    *,
    stage: str,
    run_id: str | None,
) -> int:
    """Embed (owner_id, text) pairs that have no embedding yet. Returns the number embedded."""
    if not items:
        return 0
    ids = [i for i, _ in items]
    with ctx.db.session() as s:
        have = set(
            s.scalars(
                select(Embedding.owner_id).where(
                    Embedding.owner_type == owner_type, Embedding.owner_id.in_(ids)
                )
            )
        )
    todo = [
        (i, truncate_tokens(t, MAX_EMBED_TOKENS)) for i, t in items if i not in have and t.strip()
    ]
    if not todo:
        return 0
    vectors = await ctx.llm.embed([t for _, t in todo], stage=stage, run_id=run_id)
    model = ctx.llm.roles["embed"].model
    with ctx.db.session() as s:
        for (owner_id, _), vec in zip(todo, vectors, strict=True):
            s.merge(
                Embedding(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    model=model,
                    dim=len(vec),
                    vector=to_blob(vec),
                )
            )
    return len(todo)


async def embed_query(ctx: AppContext, text: str, run_id: str | None, stage: str) -> np.ndarray:
    (vec,) = await ctx.llm.embed(
        [truncate_tokens(text, MAX_EMBED_TOKENS)], stage=stage, run_id=run_id
    )
    return np.asarray(vec, dtype=np.float32)
