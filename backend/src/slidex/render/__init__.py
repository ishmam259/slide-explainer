"""Renderer registry: ExplanationDocumentModel → file bytes per format.

Markdown is implemented here; HTML/PDF/DOCX register themselves when added (tasks T079–T081).
"""

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
    from slidex.render import markdown  # noqa: F401 — registers "md"

    return set(RENDERERS)
