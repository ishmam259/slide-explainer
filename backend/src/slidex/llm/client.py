"""OpenAI access for every model call: structured parse, embeddings, web search.

All calls go through here so that caching (FR-030), cost recording (FR-031), retries,
the model allow-list, and error mapping (FR-033) are applied uniformly.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import openai
from pydantic import BaseModel, ValidationError

from slidex.core.config import Settings
from slidex.core.errors import SlidexError
from slidex.core.models import ChatRole, ModelSpec, resolve_roles
from slidex.core.pricing import CostLedger, Usage

Detail = Literal["low", "high", "auto"]
Sleep = Callable[[float], Awaitable[None]]

MAX_ATTEMPTS = 5
EMBED_BATCH = 128


@dataclass(frozen=True)
class ImageInput:
    """An image sent to a vision-capable model. `sha256` keys the cache."""

    data: bytes
    sha256: str
    mime: str = "image/png"
    detail: Detail = "high"

    def data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode('ascii')}"


@dataclass(frozen=True)
class UrlCitation:
    url: str
    title: str


@dataclass(frozen=True)
class SearchResult:
    text: str
    citations: list[UrlCitation] = field(default_factory=list)


class CallCache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def put(self, key: str, model: str, output: Any, usage: Usage) -> None: ...


class InMemoryCallCache:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def put(self, key: str, model: str, output: Any, usage: Usage) -> None:
        self._data[key] = output


class LLM(Protocol):
    """What the pipeline depends on. Implemented by OpenAIClient and FakeLLM."""

    roles: dict[Any, ModelSpec]

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
    ) -> T: ...

    async def embed(
        self, texts: Sequence[str], *, stage: str, run_id: str | None = None
    ) -> list[list[float]]: ...

    async def search(
        self,
        query: str,
        *,
        instructions: str,
        stage: str,
        allowed_domains: Sequence[str] | None = None,
        run_id: str | None = None,
    ) -> SearchResult: ...


def cache_key(model: str, prompt_version: str, payload: Any, image_hashes: Sequence[str]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    raw = "\x1f".join([model, prompt_version, canonical, *image_hashes])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _usage_from(resp_usage: Any) -> Usage:
    if resp_usage is None:
        return Usage()
    details = getattr(resp_usage, "input_tokens_details", None)
    return Usage(
        input_tokens=int(getattr(resp_usage, "input_tokens", 0) or 0),
        cached_tokens=int(getattr(details, "cached_tokens", 0) or 0) if details else 0,
        output_tokens=int(getattr(resp_usage, "output_tokens", 0) or 0),
    )


class OpenAIClient:
    def __init__(
        self,
        settings: Settings,
        *,
        cache: CallCache,
        ledger: CostLedger,
        sdk: Any | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not settings.api_key_configured:
            raise SlidexError(
                "api_key_missing",
                "Add OPENAI_API_KEY to backend/.env (see .env.example) and restart the backend.",
            )
        self.roles = resolve_roles(settings)
        self._cache = cache
        self._ledger = ledger
        self._sleep = sleep
        self._sem = asyncio.Semaphore(settings.concurrency)
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        self._sdk = sdk if sdk is not None else openai.AsyncOpenAI(api_key=key, max_retries=0)

    async def _with_retries[R](self, call: Callable[[], Awaitable[R]]) -> R:
        for attempt in range(MAX_ATTEMPTS):
            try:
                async with self._sem:
                    return await call()
            except openai.AuthenticationError as exc:
                raise SlidexError(
                    "api_key_invalid",
                    "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env.",
                ) from exc
            except openai.PermissionDeniedError as exc:
                raise SlidexError("model_not_allowed", str(exc)) from exc
            except (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    code = (
                        "rate_limited"
                        if isinstance(exc, openai.RateLimitError)
                        else ("provider_unavailable")
                    )
                    raise SlidexError(code, str(exc)) from exc
                await self._sleep(min(30.0, 2**attempt + random.random()))  # noqa: S311
        raise AssertionError("unreachable")

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
        spec = self.roles[role]
        key = cache_key(
            spec.model,
            prompt_version,
            {
                "instructions": instructions,
                "input": input_text,
                "schema": schema.__name__,
                "effort": spec.effort,
                "detail": [i.detail for i in images],
            },
            [i.sha256 for i in images],
        )
        cached = self._cache.get(key)
        if cached is not None:
            return schema.model_validate(cached)

        content: list[dict[str, Any]] = [{"type": "input_text", "text": input_text}]
        content += [
            {"type": "input_image", "image_url": img.data_url(), "detail": img.detail}
            for img in images
        ]
        kwargs: dict[str, Any] = {
            "model": spec.model,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "text_format": schema,
        }
        if spec.effort is not None:
            kwargs["reasoning"] = {"effort": spec.effort}

        for attempt in range(2):
            response = await self._with_retries(lambda: self._sdk.responses.parse(**kwargs))
            usage = _usage_from(getattr(response, "usage", None))
            self._ledger.record(run_id, stage, spec.model, usage)
            parsed = getattr(response, "output_parsed", None)
            try:
                result = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
            except ValidationError:
                result = None
            if result is not None:
                self._cache.put(key, spec.model, result.model_dump(mode="json"), usage)
                return result
            if attempt == 1:
                break
        raise SlidexError(
            "provider_unavailable",
            f"The model returned output that does not match {schema.__name__} (after a retry).",
        )

    async def embed(
        self, texts: Sequence[str], *, stage: str, run_id: str | None = None
    ) -> list[list[float]]:
        spec = self.roles["embed"]
        out: list[list[float] | None] = [None] * len(texts)
        missing: list[int] = []
        keys = [cache_key(spec.model, "embed.v1", t, []) for t in texts]
        for i, k in enumerate(keys):
            hit = self._cache.get(k)
            if hit is not None:
                out[i] = hit
            else:
                missing.append(i)
        for start in range(0, len(missing), EMBED_BATCH):
            batch = missing[start : start + EMBED_BATCH]
            inputs = [texts[i] for i in batch]
            resp = await self._with_retries(
                lambda inputs=inputs: self._sdk.embeddings.create(model=spec.model, input=inputs)
            )
            tokens = int(getattr(getattr(resp, "usage", None), "prompt_tokens", 0) or 0)
            self._ledger.record(run_id, stage, spec.model, Usage(input_tokens=tokens))
            for i, item in zip(batch, resp.data, strict=True):
                vec = list(item.embedding)
                out[i] = vec
                self._cache.put(keys[i], spec.model, vec, Usage())
        return [v for v in out if v is not None]

    async def search(
        self,
        query: str,
        *,
        instructions: str,
        stage: str,
        allowed_domains: Sequence[str] | None = None,
        run_id: str | None = None,
    ) -> SearchResult:
        spec = self.roles["search"]
        tool: dict[str, Any] = {"type": "web_search"}
        if allowed_domains:
            tool["filters"] = {"allowed_domains": list(allowed_domains)}
        key = cache_key(spec.model, "search.v1", {"q": query, "d": allowed_domains}, [])
        cached = self._cache.get(key)
        if cached is not None:
            return SearchResult(
                text=cached["text"], citations=[UrlCitation(**c) for c in cached["citations"]]
            )
        kwargs: dict[str, Any] = {
            "model": spec.model,
            "instructions": instructions,
            "input": query,
            "tools": [tool],
        }
        if spec.effort is not None:
            kwargs["reasoning"] = {"effort": spec.effort}
        try:
            resp = await self._with_retries(lambda: self._sdk.responses.create(**kwargs))
        except SlidexError as exc:
            if exc.code == "provider_unavailable":
                raise SlidexError("search_unavailable", exc.detail) from exc
            raise
        tool_calls = sum(1 for o in resp.output if getattr(o, "type", "") == "web_search_call")
        usage = _usage_from(getattr(resp, "usage", None))
        self._ledger.record(
            run_id,
            stage,
            spec.model,
            Usage(usage.input_tokens, usage.cached_tokens, usage.output_tokens, tool_calls),
        )
        citations: list[UrlCitation] = []
        seen: set[str] = set()
        for item in resp.output:
            for part in getattr(item, "content", None) or []:
                for ann in getattr(part, "annotations", None) or []:
                    if getattr(ann, "type", "") == "url_citation" and ann.url not in seen:
                        seen.add(ann.url)
                        citations.append(UrlCitation(url=ann.url, title=ann.title or ann.url))
        result = SearchResult(text=getattr(resp, "output_text", "") or "", citations=citations)
        self._cache.put(
            key,
            spec.model,
            {"text": result.text, "citations": [c.__dict__ for c in citations]},
            usage,
        )
        return result
