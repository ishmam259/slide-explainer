"""Image decks: EXIF orientation, RGB, longest side ≤ 2000 px, stored as PNG."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from slidex.core.errors import SlidexError
from slidex.db.files import FileStore
from slidex.intake.common import SlideData

MAX_SIDE = 2000


def normalize_image(data: bytes) -> bytes:
    img: Image.Image
    try:
        opened = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(opened) or opened
    except (UnidentifiedImageError, OSError) as exc:
        raise SlidexError("corrupt_file", "An image could not be read.") from exc
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def read_images(paths: list[Path], files: FileStore) -> list[SlideData]:
    return [
        SlideData(
            number=i,
            image_hash=files.put_bytes(normalize_image(p.read_bytes()), "png"),
            image_only=True,
        )
        for i, p in enumerate(paths, start=1)
    ]
