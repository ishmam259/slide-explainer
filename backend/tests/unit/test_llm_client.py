"""OpenAI client wrapper behaviour, tested against a stub SDK (never the network)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel

from slidex.core.config import get_settings
from slidex.core.errors import SlidexError
from slidex.core.pricing import CostLedger
from slidex.llm.client import InMemoryCallCache, OpenAIClient


class Answer(BaseModel):
    text: str


@dataclass
class _Details:
    cached_tokens: int = 0


@dataclass
class _UsageStub:
    input_tokens: int = 100
    output_tokens: int = 50
    input_tokens_details: _Details = field(default_factory=_Details)


@dataclass
class _ParsedResponse:
    output_parsed: Any
    usage: _UsageStub = field(default_factory=_UsageStub)


class _Responses:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> _ParsedResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _ParsedResponse(output_parsed=outcome)


class _Sdk:
    def __init__(self, outcomes: list[Any]) -> None:
        self.responses = _Responses(outcomes)


def _rate_limit() -> openai.RateLimitError:
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=req), body=None)


def _auth_error() -> openai.AuthenticationError:
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=req), body=None
    )


async def _no_sleep(_: float) -> None:
    return None


def _client(outcomes: list[Any], ledger: CostLedger | None = None) -> tuple[OpenAIClient, _Sdk]:
    sdk = _Sdk(outcomes)
    client = OpenAIClient(
        get_settings(),
        sdk=sdk,
        cache=InMemoryCallCache(),
        ledger=ledger or CostLedger(web_search_fee=0.0),
        sleep=_no_sleep,
    )
    return client, sdk


async def _ask(client: OpenAIClient, text: str = "q") -> Answer:
    return await client.parse(
        role="bulk",
        stage="test",
        prompt_version="t.v1",
        instructions="answer",
        input_text=text,
        schema=Answer,
    )


async def test_parse_returns_validated_model_and_sends_reasoning_effort() -> None:
    client, sdk = _client([Answer(text="ok")])
    result = await _ask(client)
    assert result == Answer(text="ok")
    call = sdk.responses.calls[0]
    assert call["model"] == "gpt-5.4-nano"
    assert call["text_format"] is Answer
    assert call["reasoning"] == {"effort": "none"}


async def test_invalid_output_retried_once_then_error() -> None:
    client, sdk = _client([None, None])
    with pytest.raises(SlidexError) as exc:
        await _ask(client)
    assert exc.value.code == "provider_unavailable"
    assert len(sdk.responses.calls) == 2


async def test_invalid_output_then_valid_succeeds() -> None:
    client, _ = _client([None, Answer(text="second")])
    assert (await _ask(client)).text == "second"


async def test_cache_hit_skips_call_and_costs_nothing() -> None:
    ledger = CostLedger(web_search_fee=0.0)
    client, sdk = _client([Answer(text="once")], ledger=ledger)
    first = await _ask(client, "same")
    second = await _ask(client, "same")
    assert first == second
    assert len(sdk.responses.calls) == 1
    assert len(ledger.entries) == 1


async def test_rate_limit_backoff_then_success() -> None:
    client, sdk = _client([_rate_limit(), _rate_limit(), Answer(text="finally")])
    assert (await _ask(client)).text == "finally"
    assert len(sdk.responses.calls) == 3


async def test_rate_limit_exhausted_maps_to_problem_code() -> None:
    client, _ = _client([_rate_limit()] * 6)
    with pytest.raises(SlidexError) as exc:
        await _ask(client)
    assert exc.value.code == "rate_limited"


async def test_auth_error_maps_to_api_key_invalid() -> None:
    client, _ = _client([_auth_error()])
    with pytest.raises(SlidexError) as exc:
        await _ask(client)
    assert exc.value.code == "api_key_invalid"


async def test_usage_recorded_to_ledger() -> None:
    ledger = CostLedger(web_search_fee=0.0)
    client, _ = _client([Answer(text="ok")], ledger=ledger)
    await client.parse(
        role="strong",
        stage="explanation",
        prompt_version="t.v1",
        instructions="x",
        input_text="y",
        schema=Answer,
        run_id="run-1",
    )
    assert ledger.by_stage("run-1") == {"explanation": pytest.approx(100 * 0.2e-6 + 50 * 1.25e-6)}


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(SlidexError) as exc:
        OpenAIClient(get_settings(), cache=InMemoryCallCache(), ledger=CostLedger(web_search_fee=0))
    assert exc.value.code == "api_key_missing"
