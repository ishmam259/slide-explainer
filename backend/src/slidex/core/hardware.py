"""Detect optional local capabilities: CUDA GPU (local OCR), LibreOffice, Chromium."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from slidex.core.config import Settings


@dataclass(frozen=True)
class GpuInfo:
    available: bool
    name: str | None


@lru_cache(maxsize=1)
def detect_gpu() -> GpuInfo:
    """CUDA is usable only if onnxruntime(-gpu) exposes CUDAExecutionProvider."""
    try:
        import onnxruntime

        providers = onnxruntime.get_available_providers()
    except Exception:
        return GpuInfo(available=False, name=None)
    if "CUDAExecutionProvider" not in providers:
        return GpuInfo(available=False, name=None)
    return GpuInfo(available=True, name=_nvidia_name())


def _nvidia_name() -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(  # noqa: S603 — fixed executable and args
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else None


def libreoffice_path(settings: Settings) -> Path | None:
    if settings.soffice.is_file():
        return settings.soffice
    found = shutil.which("soffice")
    return Path(found) if found else None


def chromium_installed() -> bool:
    """True when Playwright's Chromium has been downloaded (`playwright install chromium`)."""
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if root and root != "0":
        base = Path(root)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        base = Path.home() / ".cache" / "ms-playwright"
    return base.is_dir() and any(base.glob("chromium*"))
