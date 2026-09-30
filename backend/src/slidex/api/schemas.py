"""API response/request models. Class names match `components.schemas` in the contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from slidex.core.errors import ProblemCode


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None
    code: ProblemCode


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    api_key_configured: bool
    ocr_path: Literal["local_gpu", "provider"]
    gpu_name: str | None = None
    libreoffice: bool
    renderer: bool
    models: dict[str, str]


class StageEstimate(BaseModel):
    stage: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    tool_calls: int = 0
    usd: float
    path: Literal["provider", "local"] = "provider"


class RunEstimateBudget(BaseModel):
    topics: int
    searches_per_topic: int
    pages_per_topic: int


class RunEstimate(BaseModel):
    stages: list[StageEstimate]
    total_usd: float
    est_minutes: float
    budget: RunEstimateBudget | None = None


RunKind = Literal["extract", "research", "process_sources", "generate", "qa"]
RunStatus = Literal["running", "paused", "completed", "failed", "cancelled"]


class Run(BaseModel):
    id: str
    deck_id: str
    kind: RunKind
    status: RunStatus
    stage: str | None = None
    progress: float = Field(default=0.0, ge=0, le=1)
    estimate: RunEstimate | None = None
    cost_usd: float = 0.0
    cost_by_stage: dict[str, float] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    error: Problem | None = None
