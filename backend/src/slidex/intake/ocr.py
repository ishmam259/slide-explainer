"""Text recognition for image-only slides (FR-004, FR-032).

With an NVIDIA GPU (onnxruntime CUDA provider) RapidOCR runs locally at no provider cost.
Otherwise nothing runs here: the per-slide vision extraction reads the text instead.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from functools import cache
from typing import Any

from slidex.core.hardware import detect_gpu

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


@cache
def _engine() -> Any | None:
    if not detect_gpu().available:
        return None
    try:
        from rapidocr import RapidOCR

        return RapidOCR(params={"EngineConfig.onnxruntime.use_cuda": True})
    except Exception as exc:
        log.warning("Local OCR unavailable (%s); falling back to provider vision", exc)
        return None


def local_ocr_available() -> bool:
    return _engine() is not None


def recognize(png: bytes) -> OcrResult | None:
    """Return recognized text + mean confidence, or None when local OCR is not available."""
    engine = _engine()
    if engine is None:
        return None
    import numpy as np
    from PIL import Image

    result = engine(np.asarray(Image.open(io.BytesIO(png)).convert("RGB")))
    texts = list(getattr(result, "txts", None) or [])
    scores = [float(s) for s in (getattr(result, "scores", None) or [])]
    if not texts:
        return OcrResult(text="", confidence=0.0)
    return OcrResult(text="\n".join(texts), confidence=sum(scores) / max(len(scores), 1))
