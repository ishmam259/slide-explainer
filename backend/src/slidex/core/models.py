"""Model roles and the allow-list (the learner's key allows up to GPT-5.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from slidex.core.config import Effort, Settings
from slidex.core.errors import SlidexError

ChatRole = Literal["strong", "vision", "bulk", "search"]
Role = Literal["strong", "vision", "bulk", "search", "embed"]
CHAT_ROLES: tuple[ChatRole, ...] = ("strong", "vision", "bulk", "search")

CHAT_MODELS: frozenset[str] = frozenset(
    {
        "gpt-5.4-nano",
        "gpt-5.4-nano-2026-03-17",
        "gpt-5.4-mini",
        "gpt-5.4-mini-2026-03-17",
        "gpt-5.5",
        "gpt-5.5-2026-04-23",
    }
)
EMBEDDING_MODELS: frozenset[str] = frozenset({"text-embedding-3-small", "text-embedding-3-large"})
ALLOWED_MODELS: frozenset[str] = CHAT_MODELS | EMBEDDING_MODELS

EMBEDDING_DIMS: dict[str, int] = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}


@dataclass(frozen=True)
class ModelSpec:
    role: Role
    model: str
    effort: Effort | None


def resolve_roles(settings: Settings) -> dict[Role, ModelSpec]:
    """Resolve every role to a model, rejecting anything outside the allow-list."""
    chat: dict[ChatRole, tuple[str, Effort]] = {
        "strong": (settings.model_strong, settings.effort_strong),
        "vision": (settings.model_vision, settings.effort_vision),
        "bulk": (settings.model_bulk, settings.effort_bulk),
        "search": (settings.model_search, settings.effort_search),
    }
    roles: dict[Role, ModelSpec] = {}
    for role, (model, effort) in chat.items():
        if model not in CHAT_MODELS:
            raise SlidexError(
                "model_not_allowed",
                f"Role '{role}' is set to '{model}'. Allowed chat models (up to GPT-5.5): "
                f"{', '.join(sorted(CHAT_MODELS))}.",
            )
        roles[role] = ModelSpec(role=role, model=model, effort=effort)
    if settings.model_embed not in EMBEDDING_MODELS:
        raise SlidexError(
            "model_not_allowed",
            f"Embedding role is set to '{settings.model_embed}'. Allowed: "
            f"{', '.join(sorted(EMBEDDING_MODELS))}.",
        )
    roles["embed"] = ModelSpec(role="embed", model=settings.model_embed, effort=None)
    return roles
