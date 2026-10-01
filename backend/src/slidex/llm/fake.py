"""Deterministic offline stand-in for OpenAIClient (SLIDEX_FAKE_LLM=1).

Used by all automated tests and E2E runs so they never call the paid API. Behaviour per
prompt can be supplied with `register_handler`; otherwise a minimal schema-valid instance
is generated. Embeddings are hashed bag-of-words vectors, so similar texts are close.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import types
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

from annotated_types import MaxLen, MinLen
from pydantic import BaseModel

from slidex.core.config import Settings
from slidex.core.models import ChatRole, resolve_roles
from slidex.core.pricing import CostLedger, Usage
from slidex.llm.client import ImageInput, SearchResult, UrlCitation

EMBED_DIM = 1536
_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class FakeRequest:
    role: ChatRole
    stage: str
    prompt_version: str
    instructions: str
    input_text: str
    images: Sequence[ImageInput]


Handler = Callable[[FakeRequest, type[BaseModel]], BaseModel]
_HANDLERS: dict[str, Handler] = {}


def register_handler(prompt_version: str) -> Callable[[Handler], Handler]:
    """Decorator: `@register_handler("slide_extract.v1")`."""

    def deco(fn: Handler) -> Handler:
        _HANDLERS[prompt_version] = fn
        return fn

    return deco


def fake_embedding(text: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    for word in _WORD.findall(text.lower()):
        h = int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big")
        vec[h % EMBED_DIM] += 1.0 if (h >> 63) == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeLLM:
    def __init__(
        self,
        settings: Settings,
        *,
        ledger: CostLedger,
        recordings_dir: Path | None = None,
        search_fixture: Path | None = None,
    ) -> None:
        from slidex.llm import fake_handlers  # noqa: F401 — registers prompt handlers

        self.roles = resolve_roles(settings)
        self._ledger = ledger
        self._recordings = recordings_dir
        self._search_fixture = search_fixture
        self.calls: list[FakeRequest] = []

    async def parse[T: BaseModel](
        self,
        *,
        role: ChatRole,
        stage: str,
        prompt_version: str,
        instructions: str,
        input_text: str,
        schema: type[T],
        images: Sequence[ImageInput] = (),
        run_id: str | None = None,
    ) -> T:
        req = FakeRequest(role, stage, prompt_version, instructions, input_text, images)
        self.calls.append(req)
        self._ledger.record(run_id, stage, self.roles[role].model, _approx_usage(input_text))
        recorded = self._recorded(prompt_version, input_text)
        if recorded is not None:
            return schema.model_validate(recorded)
        handler = _HANDLERS.get(prompt_version)
        if handler is not None:
            return schema.model_validate(handler(req, schema).model_dump())
        return schema.model_validate(minimal_instance(schema))

    async def embed(
        self, texts: Sequence[str], *, stage: str, run_id: str | None = None
    ) -> list[list[float]]:
        tokens = sum(len(t) // 4 for t in texts)
        self._ledger.record(run_id, stage, self.roles["embed"].model, Usage(input_tokens=tokens))
        return [fake_embedding(t) for t in texts]

    async def search(
        self,
        query: str,
        *,
        instructions: str,
        stage: str,
        allowed_domains: Sequence[str] | None = None,
        run_id: str | None = None,
    ) -> SearchResult:
        self._ledger.record(run_id, stage, self.roles["search"].model, Usage(tool_calls=1))
        if self._search_fixture is None or not self._search_fixture.is_file():
            return SearchResult(text="", citations=[])
        data = json.loads(self._search_fixture.read_text(encoding="utf-8"))
        results = data.get(query) or data.get("*") or []
        cites = [UrlCitation(url=r["url"], title=r.get("title", r["url"])) for r in results]
        if allowed_domains:
            cites = [c for c in cites if any(d in c.url for d in allowed_domains)]
        return SearchResult(text=f"Results for {query}", citations=cites)

    def _recorded(self, prompt_version: str, input_text: str) -> Any | None:
        if self._recordings is None:
            return None
        path = self._recordings / f"{prompt_version}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(input_text.encode()).hexdigest()
        return data.get(digest)


def _approx_usage(text: str) -> Usage:
    return Usage(input_tokens=max(1, len(text) // 4), output_tokens=50)


def minimal_instance(schema: type[BaseModel]) -> dict[str, Any]:
    """Smallest dict that validates against `schema` (handles common field shapes)."""
    out: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        min_len = next((m.min_length for m in field.metadata if isinstance(m, MinLen)), 0)
        max_len = next((m.max_length for m in field.metadata if isinstance(m, MaxLen)), None)
        out[name] = _value_for(field.annotation, min_len, max_len)
    return out


def _value_for(tp: Any, min_len: int = 0, max_len: int | None = None) -> Any:
    origin = get_origin(tp)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(tp) if a is not type(None)]
        return None if len(args) < len(get_args(tp)) else _value_for(args[0], min_len, max_len)
    if origin is Literal:
        return get_args(tp)[0]
    if origin in (list, Sequence):
        (inner,) = get_args(tp) or (str,)
        return [_value_for(inner) for _ in range(max(min_len, 0))]
    if origin is dict:
        return {}
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return minimal_instance(tp)
    if tp is str:
        text = "stub"
        return (text * max(1, min_len))[: max_len or None] if min_len else text
    if tp is bool:
        return False
    if tp is int:
        return max(min_len, 0)
    if tp is float:
        return 0.0
    return None
