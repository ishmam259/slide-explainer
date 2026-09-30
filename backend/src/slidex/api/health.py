from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from slidex.api.deps import AppContext, get_ctx
from slidex.api.schemas import Health
from slidex.core.hardware import chromium_installed, detect_gpu, libreoffice_path
from slidex.core.models import resolve_roles

router = APIRouter(tags=["system"])


@router.get("/health", operation_id="getHealth")
def get_health(ctx: Annotated[AppContext, Depends(get_ctx)]) -> Health:
    gpu = detect_gpu()
    libreoffice = libreoffice_path(ctx.settings) is not None
    renderer = chromium_installed()
    key_ok = ctx.settings.api_key_configured or ctx.settings.fake_llm
    roles = resolve_roles(ctx.settings)
    return Health(
        status="ok" if key_ok and libreoffice and renderer else "degraded",
        api_key_configured=key_ok,
        ocr_path="local_gpu" if gpu.available else "provider",
        gpu_name=gpu.name,
        libreoffice=libreoffice,
        renderer=renderer,
        models={role: spec.model for role, spec in roles.items()},
    )
