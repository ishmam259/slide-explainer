"""Explanation documents (US3): create, list, get, download."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select

from slidex.api import convert
from slidex.api import schemas as S
from slidex.api.deps import AppContext, get_ctx
from slidex.core.errors import SlidexError
from slidex.db.tables import Deck, ExplanationDocument
from slidex.estimate import estimate
from slidex.graph import generate_graph

router = APIRouter(tags=["documents"])
Ctx = Annotated[AppContext, Depends(get_ctx)]

MEDIA = {
    "pdf": ("application/pdf", "pdf"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "html": ("text/html", "html"),
    "md": ("application/zip", "zip"),
}


@router.get("/decks/{deck_id}/documents", operation_id="listDocuments")
def list_documents(deck_id: str, ctx: Ctx) -> list[S.ExplanationDocument]:
    with ctx.db.session() as s:
        docs = list(
            s.scalars(
                select(ExplanationDocument)
                .where(ExplanationDocument.deck_id == deck_id)
                .order_by(ExplanationDocument.created_at.desc())
            )
        )
    return [convert.document_out(ctx, d) for d in docs]


@router.post("/decks/{deck_id}/documents", operation_id="createDocument", status_code=202)
def create_document(deck_id: str, body: S.DocumentIn, ctx: Ctx) -> S.ExplanationDocument:
    if body.slide_range and body.slide_range[0] > body.slide_range[1]:
        raise SlidexError("validation_error", "slide_range must be [from, to] with from ≤ to.")
    est = estimate(ctx, deck_id, "generate").model_dump(mode="json")
    doc_id, _ = generate_graph.start_generation(
        ctx, deck_id, body.organization, list(dict.fromkeys(body.formats)), body.slide_range, est
    )
    return get_document(doc_id, ctx)


@router.get("/documents/{document_id}", operation_id="getDocument")
def get_document(document_id: str, ctx: Ctx) -> S.ExplanationDocument:
    with ctx.db.session() as s:
        doc = s.get(ExplanationDocument, document_id)
        if doc is None:
            raise SlidexError("not_found", f"Document {document_id} not found")
    return convert.document_out(ctx, doc)


@router.get(
    "/documents/{document_id}/download/{format}",
    operation_id="downloadDocument",
    response_class=FileResponse,
)
def download(
    document_id: str, format: Literal["pdf", "docx", "md", "html"], ctx: Ctx
) -> FileResponse:
    with ctx.db.session() as s:
        doc = s.get(ExplanationDocument, document_id)
        if doc is None or format not in doc.files:
            raise SlidexError("not_found", f"No {format} file for this document.")
        deck = s.get(Deck, doc.deck_id)
        title = deck.title if deck else "explanation"
    media, ext = MEDIA[format]
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip() or "explanation"
    return FileResponse(
        ctx.files.path(doc.files[format]), media_type=media, filename=f"{safe} - explained.{ext}"
    )
