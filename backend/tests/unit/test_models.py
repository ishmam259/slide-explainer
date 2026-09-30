import pytest

from slidex.core.config import get_settings
from slidex.core.errors import SlidexError
from slidex.core.models import ALLOWED_MODELS, resolve_roles


def test_defaults_are_nano_for_every_chat_role() -> None:
    roles = resolve_roles(get_settings())
    for role in ("strong", "vision", "bulk", "search"):
        assert roles[role].model == "gpt-5.4-nano"
    assert roles["embed"].model == "text-embedding-3-small"
    assert roles["strong"].effort == "medium"
    assert roles["vision"].effort == "low"
    assert roles["bulk"].effort == "none"
    assert roles["search"].effort == "low"
    assert roles["embed"].effort is None


def test_env_override_per_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLIDEX_MODEL_STRONG", "gpt-5.5")
    monkeypatch.setenv("SLIDEX_EFFORT_STRONG", "high")
    get_settings.cache_clear()
    roles = resolve_roles(get_settings())
    assert roles["strong"].model == "gpt-5.5"
    assert roles["strong"].effort == "high"
    assert roles["vision"].model == "gpt-5.4-nano"


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna", "o1-pro"])
def test_models_above_cap_are_rejected(monkeypatch: pytest.MonkeyPatch, model: str) -> None:
    monkeypatch.setenv("SLIDEX_MODEL_VISION", model)
    get_settings.cache_clear()
    with pytest.raises(SlidexError) as exc:
        resolve_roles(get_settings())
    assert exc.value.code == "model_not_allowed"


def test_embedding_model_cannot_be_used_for_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLIDEX_MODEL_BULK", "text-embedding-3-small")
    get_settings.cache_clear()
    with pytest.raises(SlidexError) as exc:
        resolve_roles(get_settings())
    assert exc.value.code == "model_not_allowed"


@pytest.mark.parametrize(
    "model", ["gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.5", "text-embedding-3-small"]
)
def test_allowed_models(model: str) -> None:
    assert model in ALLOWED_MODELS
