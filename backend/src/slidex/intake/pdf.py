"""PDF decks: per-page text (reading order), 150-DPI render, image-only detection."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from slidex.core.errors import SlidexError
from slidex.db.files import FileStore
from slidex.intake.common import IMAGE_ONLY_CHARS, MAX_SLIDES, RENDER_DPI, SlideData


def page_text(page: pymupdf.Page) -> str:
    """Text blocks sorted top-to-bottom, left-to-right."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0]  # 0 = text block
    blocks.sort(key=lambda b: (round(float(b[1]) / 10), float(b[0])))
    return "\n".join(str(b[4]).strip() for b in blocks if str(b[4]).strip())


def read_pdf(path: Path, files: FileStore, *, with_text: bool = True) -> list[SlideData]:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise SlidexError("corrupt_file", "The PDF could not be opened.") from exc
    with doc:
        if doc.needs_pass:
            raise SlidexError("corrupt_file", "The PDF is password protected.")
        if doc.page_count > MAX_SLIDES:
            raise SlidexError("too_many_slides", f"{doc.page_count} pages; the limit is 300.")
        out: list[SlideData] = []
        for i, page in enumerate(doc.pages(), start=1):
            text = page_text(page) if with_text else ""
            png = page.get_pixmap(dpi=RENDER_DPI).tobytes("png")
            out.append(
                SlideData(
                    number=i,
                    image_hash=files.put_bytes(png, "png"),
                    native_text=text,
                    image_only=with_text and len(text.strip()) < IMAGE_ONLY_CHARS,
                )
            )
    return out
