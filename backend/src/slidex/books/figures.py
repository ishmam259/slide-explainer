"""Capture and explain book figures: raster images and vector drawings (FR-015, research R7).

* Raster: `page.get_image_rects()` for each embedded image.
* Vector: `page.cluster_drawings()` groups drawing paths into figure-sized boxes.
* Regions under 5% of the page or smaller than 80 px are dropped; images repeated on ≥ 3 pages
  (logos, headers) are decorative.
* Caption = nearest text block (below, else above) starting with Figure/Fig./Table.
* Each figure is rendered at 200 DPI and explained by the vision role with nearby page text.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from sqlalchemy import delete

from slidex.api.deps import AppContext
from slidex.db.tables import Visual
from slidex.llm.client import ImageInput
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import SlideVisual

PROMPT = "figure_explain.v1"
MIN_AREA_FRACTION = 0.05
MIN_SIDE_PX = 80
DECORATIVE_REPEAT = 3
FIGURE_DPI = 200
MAX_FIGURES = 60
_CAPTION = re.compile(r"^\s*(figure|fig\.|table)\s*\d", re.IGNORECASE)


@dataclass(frozen=True)
class FigureRegion:
    page_index: int
    page_label: str
    label_kind: str
    rect: tuple[float, float, float, float]
    caption: str | None
    context: str
    decorative: bool


def _caption(page: pymupdf.Page, rect: pymupdf.Rect) -> str | None:
    best: tuple[float, str] | None = None
    for b in page.get_text("blocks"):
        text = str(b[4]).strip()
        if not _CAPTION.match(text):
            continue
        top, bottom = float(b[1]), float(b[3])
        dist = top - rect.y1 if top >= rect.y1 else (rect.y0 - bottom) + 1000  # prefer below
        if dist >= -5 and (best is None or dist < best[0]):
            best = (dist, " ".join(text.split()))
    return best[1] if best else None


def find_figures(path: Path) -> list[FigureRegion]:
    regions: list[FigureRegion] = []
    with pymupdf.open(path) as doc:
        xref_pages: Counter[int] = Counter()
        for page in doc.pages():
            for img in page.get_images(full=True):
                xref_pages[int(img[0])] += 1
        for page in doc.pages():
            page_area = page.rect.width * page.rect.height
            label = page.get_label() or str((page.number or 0) + 1)
            kind = "printed" if page.get_label() else "physical"
            text = str(page.get_text("text"))[:1500]
            rects: list[tuple[pymupdf.Rect, bool]] = []
            for img in page.get_images(full=True):
                for r in page.get_image_rects(img[0]):
                    rects.append((r, xref_pages[int(img[0])] >= DECORATIVE_REPEAT))
            for r in page.cluster_drawings():
                rects.append((pymupdf.Rect(r), False))
            for r, decorative in rects:
                scale = FIGURE_DPI / 72
                too_small = r.width * scale < MIN_SIDE_PX or r.height * scale < MIN_SIDE_PX
                if too_small or (r.width * r.height) / page_area < MIN_AREA_FRACTION:
                    continue
                regions.append(
                    FigureRegion(
                        page.number or 0,
                        label,
                        kind,
                        (r.x0, r.y0, r.x1, r.y1),
                        _caption(page, r),
                        text,
                        decorative,
                    )
                )
    return _dedupe(regions)


def _dedupe(regions: list[FigureRegion]) -> list[FigureRegion]:
    """Drop regions mostly contained in another region on the same page."""
    out: list[FigureRegion] = []
    for r in sorted(regions, key=lambda x: -(x.rect[2] - x.rect[0]) * (x.rect[3] - x.rect[1])):
        inner = pymupdf.Rect(r.rect)
        if any(o.page_index == r.page_index and pymupdf.Rect(o.rect).contains(inner) for o in out):
            continue
        out.append(r)
    return sorted(out, key=lambda x: (x.page_index, x.rect[1]))


def crop_png(path: Path, region: FigureRegion) -> bytes:
    with pymupdf.open(path) as doc:
        page = doc.load_page(region.page_index)
        pix = page.get_pixmap(dpi=FIGURE_DPI, clip=pymupdf.Rect(region.rect))
        return bytes(pix.tobytes("png"))


async def capture_figures(ctx: AppContext, source_id: str, path: Path, run_id: str | None) -> int:
    regions = [r for r in await asyncio.to_thread(find_figures, path) if not r.decorative]
    regions = regions[:MAX_FIGURES]
    with ctx.db.session() as s:
        s.execute(delete(Visual).where(Visual.source_id == source_id))

    async def one(r: FigureRegion) -> None:
        png = await asyncio.to_thread(crop_png, path, r)
        digest = ctx.files.put_bytes(png, "png")
        result = await ctx.llm.parse(
            role="vision",
            stage="figure_explanation",
            prompt_version=PROMPT,
            instructions=load(PROMPT),
            input_text=(
                f"Caption: {r.caption or '(none)'}\nPage {r.page_label}. Surrounding text:\n"
                + untrusted(source_id, r.context)
            ),
            schema=SlideVisual,
            images=[ImageInput(data=png, sha256=digest, detail="high")],
            run_id=run_id,
        )
        with ctx.db.session() as s:
            s.add(
                Visual(
                    origin="book",
                    source_id=source_id,
                    page_label=r.page_label,
                    page_index=r.page_index,
                    label_kind=r.label_kind,
                    bbox=list(r.rect),
                    image_hash=digest,
                    kind=result.kind,
                    caption=r.caption,
                    description=result.description,
                    conveys=result.conveys,
                    explanation=f"{result.description}\n\n{result.conveys}",
                    unreadable_parts=result.unreadable_parts,
                )
            )

    await asyncio.gather(*(one(r) for r in regions))
    return len(regions)
