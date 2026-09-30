import pytest

from slidex.core.pricing import CostLedger, Usage, cost_usd


def test_cost_formula_nano() -> None:
    # 1M uncached input @0.20 + 0 cached + 1M output @1.25
    assert cost_usd("gpt-5.4-nano", Usage(input_tokens=1_000_000, output_tokens=1_000_000)) == (
        pytest.approx(1.45)
    )


def test_cached_tokens_are_billed_at_cached_rate() -> None:
    usage = Usage(input_tokens=1_000_000, cached_tokens=400_000, output_tokens=0)
    # 600k @0.20 + 400k @0.02
    assert cost_usd("gpt-5.4-nano", usage) == pytest.approx(0.12 + 0.008)


def test_snapshot_ids_use_base_price() -> None:
    usage = Usage(input_tokens=1_000_000)
    assert cost_usd("gpt-5.4-nano-2026-03-17", usage) == cost_usd("gpt-5.4-nano", usage)


def test_tool_call_fee() -> None:
    usage = Usage(tool_calls=10)
    assert cost_usd("gpt-5.4-nano", usage, web_search_fee=0.01) == pytest.approx(0.10)


def test_embedding_price() -> None:
    assert cost_usd("text-embedding-3-small", Usage(input_tokens=1_000_000)) == pytest.approx(0.02)


def test_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        cost_usd("gpt-6-astra", Usage(input_tokens=1))


def test_ledger_aggregates_by_run_and_stage() -> None:
    ledger = CostLedger(web_search_fee=0.0)
    ledger.record("r1", "slide_extraction", "gpt-5.4-nano", Usage(input_tokens=1_000_000))
    ledger.record("r1", "slide_extraction", "gpt-5.4-nano", Usage(input_tokens=1_000_000))
    ledger.record("r1", "explanation", "gpt-5.4-nano", Usage(output_tokens=1_000_000))
    ledger.record("r2", "explanation", "gpt-5.4-nano", Usage(output_tokens=1_000_000))
    assert ledger.by_stage("r1") == {
        "slide_extraction": pytest.approx(0.40),
        "explanation": pytest.approx(1.25),
    }
    assert ledger.total("r1") == pytest.approx(1.65)
    assert ledger.total("r2") == pytest.approx(1.25)


def test_ledger_sink_receives_entries() -> None:
    seen = []
    ledger = CostLedger(web_search_fee=0.0, sink=seen.append)
    ledger.record("r1", "bulk", "gpt-5.4-nano", Usage(input_tokens=10))
    assert len(seen) == 1
    assert seen[0].run_id == "r1"
    assert seen[0].usd > 0
