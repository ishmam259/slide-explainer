"""Shared intake types and upload validation (FR-001, research.md R15)."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from slidex.core.errors import SlidexError

ALLOWED = {
    ".pptx": "pptx",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_SLIDES = 300
MAX_PPTX_UNCOMPRESSED = 1024 * 1024 * 1024
IMAGE_ONLY_CHARS = 20
RENDER_DPI = 150


@dataclass
class SlideData:
    number: int
    image_hash: str
    native_text: str = ""
    notes: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    image_only: bool = False


def kind_of(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise SlidexError(
            "unsupported_file",
            f"'{Path(filename).name}' is not supported. Use PPTX, PDF, PNG, JPG or WEBP.",
        )
    return ALLOWED[ext]


def validate_upload(files: list[tuple[str, Path]]) -> str:
    """Return the deck file kind ('pptx' | 'pdf' | 'images') or raise a specific problem."""
    if not files:
        raise SlidexError("validation_error", "Upload at least one file.")
    kinds = [kind_of(name) for name, _ in files]
    for name, path in files:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise SlidexError("file_too_large", f"'{name}' is larger than 200 MB.")
    if all(k == "image" for k in kinds):
        if len(files) > MAX_SLIDES:
            raise SlidexError("too_many_slides", f"{len(files)} images; the limit is 300.")
        return "images"
    if len(files) != 1:
        raise SlidexError("validation_error", "Upload one PPTX or PDF, or a set of images.")
    kind = kinds[0]
    if kind == "pptx":
        _check_zip(files[0][1], files[0][0])
    return kind


def _check_zip(path: Path, name: str) -> None:
    try:
        with zipfile.ZipFile(path) as z:
            total = sum(i.file_size for i in z.infolist())
    except zipfile.BadZipFile as exc:
        raise SlidexError("corrupt_file", f"'{name}' is not a valid PowerPoint file.") from exc
    if total > MAX_PPTX_UNCOMPRESSED:
        raise SlidexError("unsupported_file", f"'{name}' expands to more than 1 GB.")
