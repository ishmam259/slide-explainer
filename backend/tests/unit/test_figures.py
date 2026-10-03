import io
from pathlib import Path

import pymupdf
from PIL import Image

from slidex.books.figures import crop_png, find_figures


def _png(w: int, h: int, color: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def make_book(path: Path) -> Path:
    doc = pymupdf.open()
    logo = _png(40, 40, "black")
    for i in range(4):
        page = doc.new_page()  # 595 x 842
        page.insert_image(pymupdf.Rect(20, 20, 50, 50), stream=logo)  # repeated tiny logo
        page.insert_text((72, 760), f"Body text on page {i + 1}.")
    p0 = doc[0]
    p0.insert_image(pymupdf.Rect(72, 100, 520, 400), stream=_png(900, 600, "red"))
    p0.insert_text((72, 420), "Figure 1.2: Read and write quorums overlap.")
    p1 = doc[1]
    shape = p1.new_shape()  # a vector diagram: boxes and arrows
    shape.draw_rect(pymupdf.Rect(100, 150, 250, 250))
    shape.draw_rect(pymupdf.Rect(330, 150, 480, 250))
    shape.draw_line((250, 200), (330, 200))
    shape.draw_rect(pymupdf.Rect(100, 300, 480, 420))
    shape.finish(color=(0, 0, 0), width=1.5)
    shape.commit()
    p1.insert_text((72, 120), "Fig. 3 Replica placement on the ring.")
    doc.save(str(path))
    return path


def test_finds_raster_and_vector_figures_with_captions(tmp_path: Path) -> None:
    book = make_book(tmp_path / "book.pdf")
    figs = [f for f in find_figures(book) if not f.decorative]
    pages = {f.page_index for f in figs}
    assert pages == {0, 1}
    raster = next(f for f in figs if f.page_index == 0)
    assert raster.caption and raster.caption.startswith("Figure 1.2")
    vector = next(f for f in figs if f.page_index == 1)
    assert vector.caption and vector.caption.startswith("Fig. 3")


def test_tiny_and_repeated_images_skipped(tmp_path: Path) -> None:
    figs = find_figures(make_book(tmp_path / "book.pdf"))
    assert all((f.rect[2] - f.rect[0]) > 40 for f in figs)  # 30-pt logos never captured


def test_crop_renders_png(tmp_path: Path) -> None:
    book = make_book(tmp_path / "book.pdf")
    fig = next(f for f in find_figures(book) if f.page_index == 0)
    img = Image.open(io.BytesIO(crop_png(book, fig)))
    assert img.size[0] > 1000  # 200 DPI crop of a ~448-pt wide region
