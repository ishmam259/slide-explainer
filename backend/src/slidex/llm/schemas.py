"""Structured outputs for every model call (validated by the Responses API parse helper).

Shapes follow specs/001-slide-explainer/data-model.md. Keep these strict: Constitution IV
requires validated structured outputs; invalid outputs are retried, then fail loudly.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

VisualKind = Literal["diagram", "chart", "photo", "screenshot", "code", "other"]
Clarity = Literal["clear", "vague", "unreadable", "divider"]
SourceKind = Literal[
    "book", "documentation", "paper", "lecture_notes", "article", "encyclopedia", "other"
]

# ---------------------------------------------------------------- US1: slides


class Formula(BaseModel):
    latex: str
    unreadable: bool = False


class TableData(BaseModel):
    rows: list[list[str]]


class SlideVisual(BaseModel):
    id: str = Field(description="Short id unique within the slide, e.g. v1")
    kind: VisualKind
    description: str = Field(description="What is shown, part by part")
    conveys: str = Field(description="What the visual is meant to teach")
    unreadable_parts: str | None = None


class SlideExtraction(BaseModel):
    title: str | None = None
    text: str = Field(description="Cleaned slide text in reading order")
    formulas: list[Formula] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    visuals: list[SlideVisual] = Field(default_factory=list)
    topic: str
    concepts: Annotated[list[str], Field(min_length=1, max_length=12)]
    clarity: Clarity
    unreadable_regions: list[str] = Field(default_factory=list)


class InterpretationUse(BaseModel):
    neighbours: list[int] = Field(default_factory=list)
    context: bool = False
    hint: bool = False


class SlideInterpretation(BaseModel):
    meaning: Annotated[str, Field(max_length=1200)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    rationale: str
    used: InterpretationUse = Field(default_factory=InterpretationUse)


class TopicItem(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    slide_numbers: Annotated[list[int], Field(min_length=1)]


class TopicConsolidation(BaseModel):
    topics: Annotated[list[TopicItem], Field(min_length=1, max_length=15)]


# ---------------------------------------------------------------- US2: research


class QueryPlan(BaseModel):
    queries: Annotated[list[str], Field(min_length=1, max_length=2)]


class Candidate(BaseModel):
    url: str
    title: str
    kind: SourceKind
    why: Annotated[str, Field(max_length=200)]


class SearchCandidates(BaseModel):
    candidates: list[Candidate]


class SafetyVerdict(BaseModel):
    verdict: Literal["ok", "injection", "spam", "paywall"]
    reason: Annotated[str, Field(max_length=300)]


class SourceRanking(BaseModel):
    relevance: Annotated[float, Field(ge=0, le=1)]
    authority: Annotated[float, Field(ge=0, le=1)]
    kind: SourceKind
    reason: Annotated[str, Field(max_length=200)]


class Position(BaseModel):
    statement: str
    evidence_ids: Annotated[list[str], Field(min_length=1)]


class DisagreementItem(BaseModel):
    claim: str
    positions: Annotated[list[Position], Field(min_length=2)]
    involves_slide: int | None = None
    assessment: str


class DisagreementFinding(BaseModel):
    disagreements: list[DisagreementItem]


class ClusterSummary(BaseModel):
    summary: str = Field(description="Faithful summary; keep definitions and formulas")
    key_terms: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- US3: explanation

EvidenceKind = Literal["slide", "book", "web"]


class EvidenceRef(BaseModel):
    kind: EvidenceKind
    label: str
    evidence_id: str | None = None
    slide: int | None = None
    source_id: str | None = None
    page_label: str | None = None
    section_id: str | None = None
    url: str | None = None


Citations = Annotated[list[str], Field(min_length=1, description="Evidence ids from the prompt")]


class SlideSaysBlock(BaseModel):
    type: Literal["slide_says"] = "slide_says"
    text: str
    citations: Citations


class ExplanationBlock(BaseModel):
    type: Literal["explanation"] = "explanation"
    markdown: str
    citations: Citations


class DiagramBlock(BaseModel):
    type: Literal["diagram"] = "diagram"
    visual_id: str
    markdown: str
    citations: Citations


class FormulaBlock(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    steps_markdown: str
    citations: Citations


class ExampleBlock(BaseModel):
    type: Literal["example"] = "example"
    markdown: str
    citations: Citations


class ConnectionBlock(BaseModel):
    type: Literal["connection"] = "connection"
    markdown: str
    refers_to_slides: list[int] = Field(default_factory=list)
    citations: Citations


class ReconstructedBlock(BaseModel):
    type: Literal["reconstructed"] = "reconstructed"
    markdown: str
    confidence: Annotated[float, Field(ge=0, le=1)]
    citations: Citations


class DisagreementBlock(BaseModel):
    type: Literal["disagreement"] = "disagreement"
    disagreement_id: str
    markdown: str
    citations: Citations


class BookFigureBlock(BaseModel):
    type: Literal["book_figure"] = "book_figure"
    visual_id: str
    markdown: str
    citations: Citations


class ReferBackBlock(BaseModel):
    type: Literal["refer_back"] = "refer_back"
    concept: str
    slide: int


Block = Annotated[
    SlideSaysBlock
    | ExplanationBlock
    | DiagramBlock
    | FormulaBlock
    | ExampleBlock
    | ConnectionBlock
    | ReconstructedBlock
    | DisagreementBlock
    | BookFigureBlock
    | ReferBackBlock,
    Field(discriminator="type"),
]


class SlideExplanation(BaseModel):
    title: str
    blocks: Annotated[list[Block], Field(min_length=1)]


class DocSection(BaseModel):
    slide_numbers: list[int]
    title: str
    slide_image_hash: str | None = None
    blocks: list[Block]
    # Resolved citation labels for renderers: evidence id -> EvidenceRef
    evidence: dict[str, EvidenceRef] = Field(default_factory=dict)


class SourceRef(BaseModel):
    source_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    kind: str
    url: str | None = None
    publisher: str | None = None
    year: int | None = None


class ExplanationDocumentModel(BaseModel):
    title: str
    organization: Literal["by_slide", "by_topic"]
    sections: list[DocSection]
    sources: list[SourceRef] = Field(default_factory=list)
    further_reading: list[SourceRef] = Field(default_factory=list)


class FillerCheck(BaseModel):
    has_filler: bool
    offending_sentences: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- US4: Q&A and quiz


class QaAnswer(BaseModel):
    declined: bool
    text: str
    citations: list[str] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    question: str
    reference_answer: str
    evidence_ids: Annotated[list[str], Field(min_length=1)]


class QuizQuestionSet(BaseModel):
    questions: Annotated[list[QuizQuestion], Field(min_length=1, max_length=20)]


class QuizGrade(BaseModel):
    verdict: Literal["correct", "partial", "incorrect"]
    misconception: str | None = None
    hint: str | None = Field(default=None, description="Hint for the requested level only")
