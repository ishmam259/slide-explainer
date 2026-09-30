from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi.responses import FileResponse

from slidex.api.deps import AppContext, get_ctx
from slidex.core.errors import SlidexError

router = APIRouter(tags=["system"])


@router.get(
    "/files/{file_hash}",
    operation_id="getFile",
    response_class=FileResponse,
    responses={404: {"description": "Not found"}},
)
def get_file(
    file_hash: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> FileResponse:
    try:
        path = ctx.files.path(file_hash)
    except (FileNotFoundError, ValueError) as exc:
        raise SlidexError("not_found", "File not found") from exc
    return FileResponse(
        path,
        media_type=ctx.files.media_type(file_hash),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
