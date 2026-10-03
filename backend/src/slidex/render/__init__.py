"""Renderer registry: ExplanationDocumentModel → file bytes per format (md, html, pdf, docx)."""

from __future__ import annotations

from collections.abc import Callable

from slidex.db.files import FileStore
from slidex.llm.schemas import ExplanationDocumentModel

# format -> (renderer, file extension)
Renderer = Callable[[ExplanationDocumentModel, FileStore], bytes]
RENDERERS: dict[str, tuple[Renderer, str]] = {}


def register(fmt: str, ext: str) -> Callable[[Renderer], Renderer]:
    def deco(fn: Renderer) -> Renderer:
        RENDERERS[fmt] = (fn, ext)
        return fn

    return deco


def available_formats() -> set[str]:
    from slidex.render import docx, html, markdown, pdf  # noqa: F401 — registration

    return set(RENDERERS)
