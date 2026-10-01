"""Markdown renderer: document.md + images/ in a zip (FR-018)."""

from __future__ import annotations

import io
import zipfile

from slidex.db.files import FileStore
from slidex.llm.schemas import Block, DocSection, EvidenceRef, ExplanationDocumentModel
from slidex.render import register


def _cite(ids: list[str], evidence: dict[str, EvidenceRef]) -> str:
    labels = []
    for i in ids:
        ref = evidence.get(i)
        if ref is None:
            continue
        labels.append(f"[{ref.label}]({ref.url})" if ref.url else ref.label)
    return f" *({'; '.join(labels)})*" if labels else ""


def _block(b: Block, ev: dict[str, EvidenceRef]) -> str:
    cites = _cite(list(getattr(b, "citations", [])), ev)
    match b.type:
        case "slide_says":
            return f"> **What the slide says:** {b.text}{cites}"
        case "reconstructed":
            return (
                f"> **Full explanation (reconstructed from sources, confidence "
                f"{b.confidence:.0%}):**\n>\n> " + b.markdown.replace("\n", "\n> ") + cites
            )
        case "formula":
            return f"$$\n{b.latex}\n$$\n\n{b.steps_markdown}{cites}"
        case "diagram":
            return f"**Diagram ({b.visual_id}).** {b.markdown}{cites}"
        case "example":
            return f"**Example.** {b.markdown}{cites}"
        case "connection":
            return f"**Connection.** {b.markdown}{cites}"
        case "disagreement":
            return f"> **Sources disagree.** {b.markdown}{cites}"
        case "book_figure":
            return f"**Book figure.** {b.markdown}{cites}"
        case "refer_back":
            return f"*{b.concept}: see Slide {b.slide}.*"
        case _:
            return f"{b.markdown}{cites}"


def _section(sec: DocSection, images: dict[str, bytes], files: FileStore) -> str:
    out = [f"## {sec.title}"]
    if sec.slide_image_hash and files.exists(sec.slide_image_hash):
        name = f"images/slide-{sec.slide_numbers[0]}.png"
        images[name] = files.read(sec.slide_image_hash)
        out.append(f"![Slide {sec.slide_numbers[0]}]({name})")
    out += [_block(b, sec.evidence) for b in sec.blocks]
    return "\n\n".join(out)


@register("md", "zip")
def render_markdown(doc: ExplanationDocumentModel, files: FileStore) -> bytes:
    images: dict[str, bytes] = {}
    parts = [f"# {doc.title}"] + [_section(s, images, files) for s in doc.sections]
    if doc.sources:
        parts.append(
            "## Sources\n\n"
            + "\n".join(
                f"- {', '.join(s.authors) + ', ' if s.authors else ''}{s.title}"
                + (f" — {s.url}" if s.url else "")
                for s in doc.sources
            )
        )
    if doc.further_reading:
        parts.append(
            "## Further reading\n\n"
            + "\n".join(
                f"- {', '.join(s.authors) + ', ' if s.authors else ''}{s.title}"
                for s in doc.further_reading
            )
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("document.md", "\n\n".join(parts) + "\n")
        for name, data in images.items():
            z.writestr(name, data)
    return buf.getvalue()
