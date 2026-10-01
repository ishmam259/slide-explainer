"""RFC 9457 problem details. Codes mirror `Problem.code` in contracts/openapi.yaml."""

from __future__ import annotations

from typing import Literal, get_args

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ProblemCode = Literal[
    "unsupported_file",
    "corrupt_file",
    "too_many_slides",
    "file_too_large",
    "not_found",
    "invalid_state",
    "api_key_missing",
    "api_key_invalid",
    "model_not_allowed",
    "provider_unavailable",
    "rate_limited",
    "search_unavailable",
    "source_unavailable",
    "libreoffice_missing",
    "renderer_missing",
    "validation_error",
    "internal_error",
]

PROBLEM_CODES: tuple[str, ...] = get_args(ProblemCode)

_DEFAULTS: dict[str, tuple[int, str]] = {
    "unsupported_file": (415, "Unsupported file"),
    "corrupt_file": (400, "File could not be read"),
    "too_many_slides": (413, "Too many slides"),
    "file_too_large": (413, "File too large"),
    "not_found": (404, "Not found"),
    "invalid_state": (409, "Not possible in the current state"),
    "api_key_missing": (503, "OpenAI API key missing"),
    "api_key_invalid": (503, "OpenAI API key rejected"),
    "model_not_allowed": (500, "Model not allowed"),
    "provider_unavailable": (502, "AI provider unavailable"),
    "rate_limited": (429, "AI provider rate limit reached"),
    "search_unavailable": (502, "Web search unavailable"),
    "source_unavailable": (502, "Source could not be fetched"),
    "libreoffice_missing": (503, "LibreOffice not found"),
    "renderer_missing": (503, "Document renderer not installed"),
    "validation_error": (422, "Invalid request"),
    "internal_error": (500, "Unexpected error"),
}


class SlidexError(Exception):
    """An error that maps to an RFC 9457 problem response."""

    def __init__(
        self,
        code: ProblemCode,
        detail: str | None = None,
        *,
        status: int | None = None,
        title: str | None = None,
    ) -> None:
        default_status, default_title = _DEFAULTS[code]
        self.code: ProblemCode = code
        self.status = status or default_status
        self.title = title or default_title
        self.detail = detail
        super().__init__(f"{code}: {detail or self.title}")

    def to_problem(self) -> dict[str, object]:
        problem: dict[str, object] = {
            "type": f"https://slidex.local/problems/{self.code}",
            "title": self.title,
            "status": self.status,
            "code": self.code,
        }
        if self.detail:
            problem["detail"] = self.detail
        return problem


def _problem_response(problem: dict[str, object], status: int) -> JSONResponse:
    return JSONResponse(problem, status_code=status, media_type="application/problem+json")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SlidexError)
    async def _slidex_error(_: Request, exc: SlidexError) -> JSONResponse:
        return _problem_response(exc.to_problem(), exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        err = SlidexError("validation_error", "; ".join(_fmt(e) for e in exc.errors()))
        return _problem_response(err.to_problem(), err.status)


def _fmt(error: object) -> str:
    if isinstance(error, dict):
        loc = ".".join(str(p) for p in error.get("loc", ()))
        return f"{loc}: {error.get('msg', 'invalid')}"
    return str(error)
