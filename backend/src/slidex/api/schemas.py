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


# ---------------------------------------------------------------- decks & slides

Level = Literal["intro", "intermediate", "advanced", "graduate"]
DeckStatus = Literal[
    "uploaded",
    "extracting",
    "awaiting_input",
    "ready_for_research",
    "awaiting_research_confirm",
    "researching",
    "awaiting_source_approval",
    "processing_sources",
    "ready",
    "generating",
    "failed",
]
Organization = Literal["by_slide", "by_topic"]
Format = Literal["pdf", "docx", "md", "html"]


class DeckContext(BaseModel):
    course: str | None = Field(default=None, max_length=200)
    level: Level | None = None
    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class DeckSummary(BaseModel):
    id: str
    title: str
    file_kind: Literal["pptx", "pdf", "images"]
    slide_count: int
    status: DeckStatus
    created_at: datetime


class ClarityCounts(BaseModel):
    clear: int = 0
    vague: int = 0
    unreadable: int = 0
    divider: int = 0


class DeckDetail(DeckSummary):
    context: DeckContext
    clarity_counts: ClarityCounts
    needs_input_count: int
    active_run: Run | None = None
    cost_usd: float
    error: Problem | None = None


class DeckUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    context: DeckContext | None = None


class Visual(BaseModel):
    id: str
    origin: Literal["slide", "book"]
    kind: Literal["diagram", "chart", "photo", "screenshot", "code", "other"]
    image_url: str
    caption: str | None = None
    description: str = ""
    explanation: str = ""
    unreadable_parts: str | None = None
    page_label: str | None = None


class FormulaOut(BaseModel):
    latex: str
    unreadable: bool = False


class Interpretation(BaseModel):
    meaning: str
    confidence: float
    rationale: str


class Slide(BaseModel):
    number: int
    image_url: str
    title: str | None = None
    text: str = ""
    notes: str = ""
    formulas: list[FormulaOut] = Field(default_factory=list)
    visuals: list[Visual] = Field(default_factory=list)
    topic: str | None = None
    concepts: list[str] = Field(default_factory=list)
    clarity: Literal["pending", "clear", "vague", "unreadable", "divider"]
    interpretation: Interpretation | None = None
    needs_input: bool
    learner_hint: str | None = None
    unreadable_regions: list[str] = Field(default_factory=list)
    ocr_path: Literal["native", "local_ocr", "provider_vision"]


class HintIn(BaseModel):
    hint: str = Field(min_length=1, max_length=500)


class OrderIn(BaseModel):
    order: list[int]


# ---------------------------------------------------------------- research & sources


class Topic(BaseModel):
    id: str
    name: str
    slide_numbers: list[int]
    research_status: Literal["pending", "searching", "done", "no_reliable_source"]


class ResearchIn(BaseModel):
    confirm: Literal[True]
    topic_ids: list[str] | None = None


class Source(BaseModel):
    id: str
    kind: str
    origin: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    year: int | None = None
    url: str | None = None
    isbn: str | None = None
    access: Literal["usable", "further_reading", "blocked"]
    blocked_reason: str | None = None
    processing_status: str
    page_count: int | None = None


class DeckSource(BaseModel):
    source: Source
    topic_ids: list[str]
    relevance: float
    authority: float
    reason: str
    added_by: Literal["research", "learner"]
    approved: bool


class TopicSources(BaseModel):
    topic: Topic
    sources: list[DeckSource]


class SourceList(BaseModel):
    by_topic: list[TopicSources]
    further_reading: list[Source]


class SourceUpdate(BaseModel):
    approved: bool


class EvidenceRef(BaseModel):
    kind: Literal["slide", "book", "web"]
    label: str
    slide: int | None = None
    source_id: str | None = None
    page_label: str | None = None
    section_id: str | None = None
    url: str | None = None


class PositionOut(BaseModel):
    statement: str
    evidence: list[EvidenceRef]


class Disagreement(BaseModel):
    id: str
    topic_id: str
    claim: str
    involves_slide: int | None = None
    positions: list[PositionOut]
    assessment: str


# ---------------------------------------------------------------- documents


class DocumentIn(BaseModel):
    organization: Organization
    formats: list[Format] = Field(min_length=1)
    slide_range: list[int] | None = Field(default=None, min_length=2, max_length=2)


class DocStats(BaseModel):
    sections: int = 0
    reconstructed_slides: int = 0
    disagreements_shown: int = 0
    dropped_blocks: int = 0


class ExplanationDocument(BaseModel):
    id: str
    deck_id: str
    organization: Organization
    formats: list[Format]
    slide_range: list[int] | None = None
    status: Literal["queued", "generating", "rendering", "ready", "failed"]
    progress: float = 0.0
    downloads: dict[str, str] = Field(default_factory=dict)
    stats: DocStats = Field(default_factory=DocStats)
    cost_usd: float = 0.0
    created_at: datetime
    error: Problem | None = None


# ---------------------------------------------------------------- Q&A and quiz


class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = None


class QaTurn(BaseModel):
    id: str
    thread_id: str
    role: Literal["learner", "assistant"]
    text: str
    citations: list[EvidenceRef]
    declined: bool
    created_at: datetime


class QaThreadOut(BaseModel):
    id: str
    turns: list[QaTurn]


class QuizIn(BaseModel):
    slide_from: int = Field(ge=1)
    slide_to: int = Field(ge=1)
    count: int = Field(default=5, ge=1, le=20)


class QuizScore(BaseModel):
    correct: int = 0
    answered: int = 0


class QuizState(BaseModel):
    id: str
    deck_id: str
    slide_from: int
    slide_to: int
    status: Literal["active", "completed"]
    index: int
    total: int
    question: str | None = None
    hint_level: int = Field(ge=0, le=3)
    score: QuizScore


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


class QuizFeedback(BaseModel):
    verdict: Literal["correct", "partial", "incorrect", "revealed"]
    misconception: str | None = None
    hint: str | None = None
    pointer: EvidenceRef | None = None
    revealed_answer: str | None = None
    explanation: str | None = None
    citations: list[EvidenceRef] = Field(default_factory=list)
    hint_level: int = Field(ge=0, le=3)
    state: QuizState
