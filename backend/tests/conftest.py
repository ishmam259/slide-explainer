"""Test configuration: offline by default (fake LLM, no real network), isolated data dir."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import respx

# Must be set before any slidex module reads settings.
os.environ["SLIDEX_FAKE_LLM"] = "1"
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("SLIDEX_DATA_DIR", str(data_dir))
    from slidex.core import config

    config.get_settings.cache_clear()
    yield data_dir
    config.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_real_network() -> Iterator[respx.MockRouter]:
    """Any httpx request that a test hasn't explicitly mocked fails loudly."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


FIXTURES = Path(__file__).parent / "fixtures"
