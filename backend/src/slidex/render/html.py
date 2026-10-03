"""HTML renderer: self-contained, print-friendly, DESIGN.md light theme (FR-018)."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from slidex.db.files import FileStore
from slidex.llm.schemas import Block, DocSection, EvidenceRef, ExplanationDocumentModel
from slidex.render import register
from slidex.render.browser import katex_css_inline, load_with_math, with_page

_MD = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

LABELS = {
    "slide_says": "What the slide says",
    "reconstructed": "Full explanation (reconstructed from sources)",
    "explanation": "",
    "diagram": "Diagram",
    "formula": "Formula",
    "example": "Example",
    "connection": "Connection to earlier slides",
    "disagreement": "Sources disagree",
    "book_figure": "Book figure",
}


def md(text: str) -> Markup:
    """Model text is untrusted: raw HTML is disabled, output is safe markup."""
    return Markup(_MD.render(text or ""))  # noqa: S704 — markdown-it with html disabled


def _cites(ids: list[str], ev: dict[str, EvidenceRef]) -> list[EvidenceRef]:
    return [ev[i] for i in ids if i in ev]


def _block_view(b: Block, ev: dict[str, EvidenceRef]) -> dict[str, object]:
    view: dict[str, object] = {"type": b.type, "label": LABELS.get(b.type, "")}
    view["citations"] = _cites(list(getattr(b, "citations", [])), ev)
    if b.type == "slide_says":
        view["body"] = md(b.text)
    elif b.type == "formula":
        view["latex"] = b.latex
        view["body"] = md(b.steps_markdown)
    elif b.type == "refer_back":
        view["body"] = Markup("<em>{}: see Slide {}.</em>").format(b.concept, b.slide)
    else:
        view["body"] = md(getattr(b, "markdown", ""))
    if b.type == "reconstructed":
        view["confidence"] = round(b.confidence * 100)
    return view


def _image(files: FileStore, digest: str | None) -> str | None:
    if not digest or not files.exists(digest):
        return None
    return "data:image/png;base64," + base64.b64encode(files.read(digest)).decode("ascii")


def _section_view(sec: DocSection, files: FileStore) -> dict[str, object]:
    return {
        "title": sec.title,
        "image": _image(files, sec.slide_image_hash),
        "slides": sec.slide_numbers,
        "blocks": [_block_view(b, sec.evidence) for b in sec.blocks],
    }


def build_html(doc: ExplanationDocumentModel, files: FileStore) -> str:
    template = _ENV.get_template("document.html.j2")
    return template.render(
        doc=doc,
        sections=[_section_view(s, files) for s in doc.sections],
        katex_css=Markup(katex_css_inline()),  # noqa: S704 — vendored asset
    )


@register("html", "html")
def render_html(doc: ExplanationDocumentModel, files: FileStore) -> bytes:
    """Math is rendered in a headless browser so the file needs no scripts to display."""
    html = build_html(doc, files)

    def run(page: object) -> str:
        load_with_math(page, html)  # type: ignore[arg-type]
        return str(page.evaluate("() => '<!doctype html>\\n' + document.documentElement.outerHTML"))  # type: ignore[attr-defined]

    return with_page(run).encode("utf-8")
