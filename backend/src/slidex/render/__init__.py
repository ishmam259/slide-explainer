"""Renderer registry: ExplanationDocumentModel → file bytes per format (md, html, pdf, docx)."""

from __future__ import annotations

from collections.abc import Callable

from slidex.db.files import FileStore
from slidex.llm.schemas import EvidenceRef, ExplanationDocumentModel

# format -> (renderer, file extension)
Renderer = Callable[[ExplanationDocumentModel, FileStore], bytes]
RENDERERS: dict[str, tuple[Renderer, str]] = {}


def register(fmt: str, ext: str) -> Callable[[Renderer], Renderer]:
    def deco(fn: Renderer) -> Renderer:
        RENDERERS[fmt] = (fn, ext)
        return fn

    return deco


def cited(ids: list[str], evidence: dict[str, EvidenceRef]) -> list[EvidenceRef]:
    """Evidence refs for a block, in order, without repeating the same label/link."""
    seen: set[tuple[str, str | None]] = set()
    out: list[EvidenceRef] = []
    for i in ids:
        ref = evidence.get(i)
        if ref is None or (ref.label, ref.url) in seen:
            continue
        seen.add((ref.label, ref.url))
        out.append(ref)
    return out


def available_formats() -> set[str]:
    from slidex.render import docx, html, markdown, pdf  # noqa: F401 — registration

    return set(RENDERERS)
