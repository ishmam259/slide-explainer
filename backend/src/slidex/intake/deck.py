"""Create a Deck + Slide rows from an upload (runs in a worker thread: CPU/IO heavy)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from slidex.api.deps import AppContext
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, Slide
from slidex.intake.common import SlideData, validate_upload
from slidex.intake.images import read_images
from slidex.intake.ocr import recognize
from slidex.intake.pdf import read_pdf
from slidex.intake.pptx import read_pptx


def _title(name: str, slides: list[SlideData]) -> str:
    first = next((s.native_text.splitlines()[0] for s in slides if s.native_text.strip()), "")
    return (first.strip() or Path(name).stem or "Untitled deck")[:200]


def create_deck(ctx: AppContext, files: list[tuple[str, Path]], context: dict[str, Any]) -> str:
    kind = validate_upload(files)
    hashes = [ctx.files.put_file(p, Path(n).suffix.lower().lstrip(".")) for n, p in files]
    if kind == "pptx":
        slides = read_pptx(files[0][1], ctx.files, ctx.settings)
    elif kind == "pdf":
        slides = read_pdf(files[0][1], ctx.files)
    else:
        slides = read_images([p for _, p in files], ctx.files)
    if not slides:
        raise SlidexError("corrupt_file", "No slides were found in the upload.")
    ocr: dict[int, tuple[str, float]] = {}
    for s in slides:
        if s.image_only:
            res = recognize(ctx.files.read(s.image_hash))
            if res is not None:
                ocr[s.number] = (res.text, res.confidence)
    with ctx.db.session() as db:
        deck = Deck(
            title=_title(files[0][0], slides),
            file_kind="images" if kind == "images" else kind,
            file_hashes=hashes,
            context=context,
            slide_count=len(slides),
        )
        db.add(deck)
        db.flush()
        for s in slides:
            text, conf = ocr.get(s.number, (None, None))
            db.add(
                Slide(
                    deck_id=deck.id,
                    number=s.number,
                    image_hash=s.image_hash,
                    native_text=s.native_text,
                    notes=s.notes,
                    native_tables=s.tables,
                    ocr_text=text,
                    ocr_confidence=conf,
                    ocr_path="local_ocr"
                    if text is not None
                    else ("provider_vision" if s.image_only else "native"),
                )
            )
        return deck.id
