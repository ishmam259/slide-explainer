"""RAPTOR tree: leaves → soft GMM clusters (BIC) → summaries, recursively (research.md R7)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import numpy as np
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sqlalchemy import delete

from slidex.api.deps import AppContext
from slidex.books.chunk import chunk_pages
from slidex.books.parse import Page, TocEntry, parse_book
from slidex.db.tables import BookNode, Source
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import ClusterSummary
from slidex.retrieval.embed import embed_owners
from slidex.retrieval.tokens import count_tokens

PROMPT = "raptor_summary.v1"
PCA_DIMS = 32
SOFT_THRESHOLD = 0.1
MAX_CLUSTER_TOKENS = 3000
STOP_AT = 3
MAX_K = 50
SEED = 224
COVARIANCE = "diag"  # full covariance overfits small clusters (few passages, 32 dims)


@dataclass
class Node:
    id: str
    text: str
    page_start: int
    page_end: int
    vector: np.ndarray
    children: list[str] = field(default_factory=list)


def _reduce(vectors: np.ndarray) -> np.ndarray:
    x = StandardScaler().fit_transform(vectors)
    dims = min(PCA_DIMS, x.shape[0] - 1, x.shape[1])
    return PCA(n_components=dims, random_state=SEED).fit_transform(x) if dims >= 2 else x


def choose_k(x: np.ndarray, max_k: int = MAX_K) -> int:
    """Number of GMM components with the lowest BIC."""
    upper = min(max_k, len(x) - 1)
    if upper < 2:
        return 1
    bics = [
        GaussianMixture(n_components=k, covariance_type=COVARIANCE, random_state=SEED).fit(x).bic(x)
        for k in range(1, upper + 1)
    ]
    return int(np.argmin(bics)) + 1


def soft_clusters(vectors: np.ndarray, threshold: float = SOFT_THRESHOLD) -> list[list[int]]:
    """Indices per cluster; a member may belong to several clusters (p ≥ threshold)."""
    n = len(vectors)
    if n <= STOP_AT:
        return [list(range(n))]
    x = _reduce(vectors)
    k = choose_k(x)
    gmm = GaussianMixture(n_components=k, covariance_type=COVARIANCE, random_state=SEED).fit(x)
    probs = gmm.predict_proba(x)
    clusters = [[int(i) for i in np.where(probs[:, c] >= threshold)[0]] for c in range(k)]
    clusters = [c for c in clusters if c]
    assigned = {i for c in clusters for i in c}
    for i in range(n):  # guarantee every member is somewhere
        if i not in assigned:
            clusters.append([i])
    return clusters


def split_oversized(members: list[int], tokens: list[int], vectors: np.ndarray) -> list[list[int]]:
    if sum(tokens[i] for i in members) <= MAX_CLUSTER_TOKENS or len(members) <= 2:
        return [members]
    sub = soft_clusters(vectors[members])
    if len(sub) <= 1:  # cannot split further: chunk sequentially
        out, cur, cur_t = [], [], 0
        for i in members:
            if cur and cur_t + tokens[i] > MAX_CLUSTER_TOKENS:
                out.append(cur)
                cur, cur_t = [], 0
            cur.append(i)
            cur_t += tokens[i]
        return out + ([cur] if cur else [])
    result: list[list[int]] = []
    for group in sub:
        result.extend(split_oversized([members[i] for i in group], tokens, vectors))
    return result


def _label(pages: list[Page], idx: int) -> tuple[str, str]:
    p = pages[min(idx, len(pages) - 1)]
    return p.label, p.label_kind


async def build_tree(ctx: AppContext, source_id: str, run_id: str | None) -> int:
    """Build (or rebuild) the RAPTOR tree for one book source. Returns the node count."""
    with ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None and src.file_hash
        src.processing_status = "processing"
        path = ctx.files.path(src.file_hash)
        s.execute(delete(BookNode).where(BookNode.source_id == source_id))
    pages, toc = parse_book(path)
    leaves = chunk_pages(pages)
    if not leaves:
        raise ValueError("Book has no extractable text (scanned PDFs are not supported).")

    level_nodes = await _store_level(
        ctx,
        source_id,
        pages,
        0,
        "passage",
        [(lf.text, lf.page_start, lf.page_end, []) for lf in leaves],
        run_id,
    )
    total = len(level_nodes)
    if toc:
        total += await _chapter_nodes(ctx, source_id, pages, toc, level_nodes, run_id)
    level = 1
    while len(level_nodes) > STOP_AT:
        vectors = np.vstack([n.vector for n in level_nodes])
        tokens = [count_tokens(n.text) for n in level_nodes]
        groups: list[list[int]] = []
        for c in soft_clusters(vectors):
            groups.extend(split_oversized(c, tokens, vectors))
        if len(groups) >= len(level_nodes):  # no progress; stop to avoid loops
            break
        summaries = await asyncio.gather(
            *(_summarize(ctx, source_id, [level_nodes[i] for i in g], run_id) for g in groups)
        )
        specs = []
        for g, summary in zip(groups, summaries, strict=True):
            members = [level_nodes[i] for i in g]
            specs.append(
                (
                    summary,
                    min(m.page_start for m in members),
                    max(m.page_end for m in members),
                    [m.id for m in members],
                )
            )
        nodes = await _store_level(ctx, source_id, pages, level, "cluster", specs, run_id)
        total += len(nodes)
        level_nodes = nodes
        level += 1
    with ctx.db.session() as s:
        for n in level_nodes:
            row = s.get(BookNode, n.id)
            if row is not None and row.level > 0:
                row.kind = "theme"
        src = s.get(Source, source_id)
        assert src is not None
        src.processing_status = "ready"
        src.page_count = len(pages)
    return total


async def _summarize(
    ctx: AppContext, source_id: str, members: list[Node], run_id: str | None
) -> str:
    body = "\n\n".join(untrusted(source_id, m.text) for m in members)
    result = await ctx.llm.parse(
        role="bulk",
        stage="book_processing",
        prompt_version=PROMPT,
        instructions=load(PROMPT),
        input_text=body,
        schema=ClusterSummary,
        run_id=run_id,
    )
    return result.summary


async def _store_level(
    ctx: AppContext,
    source_id: str,
    pages: list[Page],
    level: int,
    kind: str,
    specs: list[tuple[str, int, int, list[str]]],
    run_id: str | None,
) -> list[Node]:
    rows: list[BookNode] = []
    with ctx.db.session() as s:
        for text, start, end, children in specs:
            ls, kind_s = _label(pages, start)
            le, _ = _label(pages, end)
            row = BookNode(
                source_id=source_id,
                level=level,
                kind=kind,
                text=text,
                page_start=ls,
                page_end=le,
                label_kind=kind_s,
                token_count=count_tokens(text),
            )
            s.add(row)
            s.flush()
            rows.append(row)
            for child in children:
                c = s.get(BookNode, child)
                if c is not None:
                    c.parent_ids = [*c.parent_ids, row.id]
    await embed_owners(
        ctx, "book_node", [(r.id, r.text) for r in rows], stage="book_processing", run_id=run_id
    )
    from slidex.db.tables import Embedding
    from slidex.retrieval.embed import from_blob

    with ctx.db.session() as s:
        vecs = {
            e.owner_id: from_blob(e.vector)
            for e in s.query(Embedding).filter(
                Embedding.owner_type == "book_node", Embedding.owner_id.in_([r.id for r in rows])
            )
        }
    return [
        Node(r.id, r.text, start, end, vecs[r.id], children)
        for r, (_, start, end, children) in zip(rows, specs, strict=True)
    ]


async def _chapter_nodes(
    ctx: AppContext,
    source_id: str,
    pages: list[Page],
    toc: list[TocEntry],
    leaves: list[Node],
    run_id: str | None,
) -> int:
    """Chapter-level summaries from the PDF outline (top-level TOC entries)."""
    chapters = [e for e in toc if e.level == 1]
    if not chapters:
        return 0
    bounds = [
        (
            c.title,
            c.page_index,
            (chapters[i + 1].page_index - 1) if i + 1 < len(chapters) else len(pages) - 1,
        )
        for i, c in enumerate(chapters)
    ]
    specs = []
    for title, start, end in bounds:
        members = [lf for lf in leaves if start <= lf.page_start <= end]
        if not members:
            continue
        summary = await _summarize(ctx, source_id, members[:40], run_id)
        specs.append((f"{title}\n{summary}", start, end, [m.id for m in members]))
    nodes = await _store_level(ctx, source_id, pages, 1, "chapter", specs, run_id)
    return len(nodes)
