"""Book processing: page labels, leaf chunking, RAPTOR levels, page ranges, TOC chapters (T051)."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.books import raptor
from slidex.books.chunk import chunk_pages
from slidex.books.parse import Page, parse_book
from slidex.db.tables import BookNode, Source
from slidex.retrieval.tokens import count_tokens

TOPICS = ["replication", "consensus", "transactions", "indexing", "caching", "sharding"]


def _paragraph(topic: str, i: int) -> str:
    return (
        f"Paragraph {i} on {topic}. " + f"The {topic} mechanism keeps data correct and fast. " * 8
    )


def _book(path: Path, *, toc: bool = True, labels: bool = True) -> Path:
    """2 front-matter pages (roman labels) + 12 body pages (arabic labels), 2 chapters."""
    doc = pymupdf.open()
    for i in range(2):
        doc.new_page().insert_text((72, 72), f"Preface page {i + 1}")
    for p in range(12):
        topic = TOPICS[p // 2]
        page = doc.new_page()
        text = "\n\n".join(_paragraph(topic, j) for j in range(3))
        page.insert_textbox(pymupdf.Rect(50, 50, 560, 800), text, fontsize=7)
    if labels:
        doc.set_page_labels(
            [
                {"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
                {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1},
            ]
        )
    if toc:
        doc.set_toc([[1, "Chapter 1: Storage", 3], [1, "Chapter 2: Scale", 9]])
    doc.save(str(path))
    doc.close()
    return path


def test_printed_page_labels(tmp_path: Path) -> None:
    pages, toc = parse_book(_book(tmp_path / "b.pdf"))
    assert [p.label for p in pages[:4]] == ["i", "ii", "1", "2"]
    assert all(p.label_kind == "printed" for p in pages)
    assert [(e.title, e.page_index) for e in toc] == [
        ("Chapter 1: Storage", 2),
        ("Chapter 2: Scale", 8),
    ]


def test_physical_labels_without_page_labels(tmp_path: Path) -> None:
    pages, toc = parse_book(_book(tmp_path / "b.pdf", toc=False, labels=False))
    assert pages[0].label == "1" and pages[0].label_kind == "physical"
    assert pages[13].label == "14"
    assert toc == []


def test_chunks_follow_paragraphs_and_target() -> None:
    para = "word " * 120
    pages = [Page(i, str(i + 1), "physical", f"{para}\n\n{para}\n\n{para}") for i in range(4)]
    leaves = chunk_pages(pages, target=350)
    assert len(leaves) > 1
    for leaf in leaves:
        assert leaf.tokens <= 350 or leaf.text.count(" \n") == 0  # only a single huge paragraph
        assert leaf.page_start <= leaf.page_end
    # paragraphs are never cut: every leaf is a whole number of paragraphs
    assert all(seg == para.strip() for leaf in leaves for seg in leaf.text.split(" \n"))
    assert sum(leaf.tokens for leaf in leaves) == 12 * count_tokens(para.strip())
    assert leaves[0].page_start == 0 and leaves[-1].page_end == 3


def test_chunk_spans_pages() -> None:
    pages = [Page(0, "1", "physical", "short one"), Page(1, "2", "physical", "short two")]
    (leaf,) = chunk_pages(pages)
    assert (leaf.page_start, leaf.page_end) == (0, 1)
    assert "short one" in leaf.text and "short two" in leaf.text


async def _built(ctx: AppContext, path: Path) -> str:
    digest = ctx.files.put_bytes(path.read_bytes(), "pdf")  # noqa: ASYNC240 — tiny test file
    with ctx.db.session() as s:
        src = Source(kind="book", origin="learner_file", title="Systems", file_hash=digest)
        s.add(src)
        s.flush()
        source_id = src.id
    await raptor.build_tree(ctx, source_id, None)
    return source_id


def _nodes(ctx: AppContext, source_id: str) -> list[BookNode]:
    with ctx.db.session() as s:
        return list(s.scalars(select(BookNode).where(BookNode.source_id == source_id)))


async def test_tree_levels_stop_at_three_with_theme_top(
    app_ctx: AppContext, tmp_path: Path
) -> None:
    source_id = await _built(app_ctx, _book(tmp_path / "b.pdf", toc=False))
    nodes = _nodes(app_ctx, source_id)
    leaves = [n for n in nodes if n.level == 0]
    assert len(leaves) > raptor.STOP_AT
    assert all(n.kind == "passage" for n in leaves)
    top_level = max(n.level for n in nodes)
    assert top_level >= 1
    top = [n for n in nodes if n.level == top_level]
    assert all(n.kind == "theme" for n in top)
    with app_ctx.db.session() as s:
        src = s.get(Source, source_id)
        assert src is not None and src.processing_status == "ready" and src.page_count == 14


async def test_parent_page_range_is_union_of_children(app_ctx: AppContext, tmp_path: Path) -> None:
    source_id = await _built(app_ctx, _book(tmp_path / "b.pdf", toc=False, labels=False))
    nodes = {n.id: n for n in _nodes(app_ctx, source_id)}
    parents: dict[str, list[BookNode]] = {}
    for n in nodes.values():
        for pid in n.parent_ids:
            parents.setdefault(pid, []).append(n)
    assert parents, "no parent links were recorded"
    for pid, children in parents.items():
        parent = nodes[pid]
        if parent.kind == "chapter":
            continue
        assert parent.page_start is not None and parent.page_end is not None
        assert int(parent.page_start) == min(int(c.page_start or 0) for c in children)
        assert int(parent.page_end) == max(int(c.page_end or 0) for c in children)


async def test_toc_creates_chapter_nodes(app_ctx: AppContext, tmp_path: Path) -> None:
    source_id = await _built(app_ctx, _book(tmp_path / "b.pdf"))
    chapters = [n for n in _nodes(app_ctx, source_id) if n.kind == "chapter"]
    assert sorted(c.text.splitlines()[0] for c in chapters) == [
        "Chapter 1: Storage",
        "Chapter 2: Scale",
    ]
    first = next(c for c in chapters if c.text.startswith("Chapter 1"))
    assert (first.page_start, first.label_kind) == ("1", "printed")


async def test_rebuild_replaces_nodes(app_ctx: AppContext, tmp_path: Path) -> None:
    source_id = await _built(app_ctx, _book(tmp_path / "b.pdf", toc=False))
    before = len(_nodes(app_ctx, source_id))
    await raptor.build_tree(app_ctx, source_id, None)
    assert len(_nodes(app_ctx, source_id)) == before
