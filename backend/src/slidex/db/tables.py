"""ORM tables — one class per entity in specs/001-slide-explainer/data-model.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from slidex.db.base import Base, new_id, utcnow

ID = String(26)


def _id() -> Mapped[str]:
    return mapped_column(ID, primary_key=True, default=new_id)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Deck(Base):
    __tablename__ = "deck"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="deck_title_len"),
        CheckConstraint("slide_count BETWEEN 0 AND 300", name="deck_slide_count"),
        CheckConstraint("file_kind IN ('pptx','pdf','images')", name="deck_file_kind"),
    )
    id: Mapped[str] = _id()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    file_hashes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Slide(Base):
    __tablename__ = "slide"
    __table_args__ = (
        UniqueConstraint("deck_id", "number", name="slide_number_unique"),
        CheckConstraint("number >= 1", name="slide_number_positive"),
        CheckConstraint(
            "clarity IN ('pending','clear','vague','unreadable','divider')", name="slide_clarity"
        ),
        CheckConstraint(
            "learner_hint IS NULL OR length(learner_hint) BETWEEN 1 AND 500", name="slide_hint_len"
        ),
        CheckConstraint(
            "ocr_path IN ('native','local_ocr','provider_vision')", name="slide_ocr_path"
        ),
    )
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    native_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    native_tables: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    clarity: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    interpretation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    needs_input: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    learner_hint: Mapped[str | None] = mapped_column(String(500))
    ocr_path: Mapped[str] = mapped_column(String(16), default="native", nullable=False)
    extraction_hash: Mapped[str | None] = mapped_column(String(64))


class Visual(Base):
    __tablename__ = "visual"
    __table_args__ = (
        CheckConstraint("origin IN ('slide','book')", name="visual_origin"),
        CheckConstraint(
            "kind IN ('diagram','chart','photo','screenshot','code','other')", name="visual_kind"
        ),
    )
    id: Mapped[str] = _id()
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("slide.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), index=True
    )
    page_label: Mapped[str | None] = mapped_column(String(32))
    page_index: Mapped[int | None] = mapped_column(Integer)
    label_kind: Mapped[str | None] = mapped_column(String(8))
    bbox: Mapped[list[float] | None] = mapped_column(JSON)
    image_hash: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    conveys: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    unreadable_parts: Mapped[str | None] = mapped_column(Text)
    decorative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Topic(Base):
    __tablename__ = "topic"
    __table_args__ = (
        CheckConstraint(
            "research_status IN ('pending','searching','done','no_reliable_source')",
            name="topic_status",
        ),
        Index("topic_name_unique", "deck_id", "name_key", unique=True),
    )
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), nullable=False)  # lower-cased name
    slide_numbers: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    research_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    queries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Source(Base):
    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('book','documentation','paper','lecture_notes','article','encyclopedia',"
            "'other')",
            name="source_kind",
        ),
        CheckConstraint(
            "origin IN ('web','learner_file','learner_url','open_library')", name="source_origin"
        ),
        CheckConstraint("access IN ('usable','further_reading','blocked')", name="source_access"),
        CheckConstraint(
            "processing_status IN ('pending','fetching','processing','ready','failed')",
            name="source_processing",
        ),
    )
    id: Mapped[str] = _id()
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    publisher: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(Text)
    url_normalized: Mapped[str | None] = mapped_column(Text, unique=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    isbn: Mapped[str | None] = mapped_column(String(20))
    access: Mapped[str] = mapped_column(String(16), default="usable", nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = _created()


class DeckSource(Base):
    __tablename__ = "deck_source"
    __table_args__ = (
        CheckConstraint("relevance BETWEEN 0 AND 1", name="ds_relevance"),
        CheckConstraint("authority BETWEEN 0 AND 1", name="ds_authority"),
        CheckConstraint("length(reason) <= 200", name="ds_reason_len"),
        CheckConstraint("added_by IN ('research','learner')", name="ds_added_by"),
    )
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), primary_key=True
    )
    topic_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    authority: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    added_by: Mapped[str] = mapped_column(String(8), default="research", nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BookNode(Base):
    __tablename__ = "book_node"
    __table_args__ = (
        CheckConstraint("kind IN ('passage','cluster','chapter','theme')", name="bn_kind"),
        CheckConstraint("level >= 0", name="bn_level"),
    )
    id: Mapped[str] = _id()
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"), index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    parent_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[str | None] = mapped_column(String(32))
    page_end: Mapped[str | None] = mapped_column(String(32))
    label_kind: Mapped[str | None] = mapped_column(String(8))
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    figure_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class WebSection(Base):
    __tablename__ = "web_section"
    id: Mapped[str] = _id()
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"), index=True)
    heading_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    anchor: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)


class Embedding(Base):
    __tablename__ = "embedding"
    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('book_node','web_section','slide','concept')", name="emb_owner"
        ),
        CheckConstraint("length(vector) = dim * 4", name="emb_len"),
    )
    owner_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class Disagreement(Base):
    __tablename__ = "disagreement"
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    positions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    involves_slide: Mapped[int | None] = mapped_column(Integer)
    assessment: Mapped[str] = mapped_column(Text, nullable=False)


class ExplanationDocument(Base):
    __tablename__ = "explanation_document"
    __table_args__ = (
        CheckConstraint("organization IN ('by_slide','by_topic')", name="doc_org"),
        CheckConstraint(
            "status IN ('queued','generating','rendering','ready','failed')", name="doc_status"
        ),
    )
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    organization: Mapped[str] = mapped_column(String(8), nullable=False)
    formats: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    slide_range: Mapped[list[int] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    files: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    stats: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    run_id: Mapped[str | None] = mapped_column(String(26))
    created_at: Mapped[datetime] = _created()


class QaThread(Base):
    __tablename__ = "qa_thread"
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = _created()


class QaTurn(Base):
    __tablename__ = "qa_turn"
    __table_args__ = (CheckConstraint("role IN ('learner','assistant')", name="qa_role"),)
    id: Mapped[str] = _id()
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("qa_thread.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    declined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = _created()


class QuizSession(Base):
    __tablename__ = "quiz_session"
    __table_args__ = (
        CheckConstraint("status IN ('active','completed')", name="quiz_status"),
        CheckConstraint("slide_from >= 1 AND slide_to >= slide_from", name="quiz_range"),
    )
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    slide_from: Mapped[int] = mapped_column(Integer, nullable=False)
    slide_to: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="active", nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = _created()


class QuizItem(Base):
    __tablename__ = "quiz_item"
    __table_args__ = (CheckConstraint("hint_level BETWEEN 0 AND 3", name="quiz_hint_level"),)
    id: Mapped[str] = _id()
    session_id: Mapped[str] = mapped_column(
        ForeignKey("quiz_session.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    hint_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Run(Base):
    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('extract','research','process_sources','generate','qa')", name="run_kind"
        ),
        CheckConstraint(
            "status IN ('running','paused','completed','failed','cancelled')", name="run_status"
        ),
    )
    id: Mapped[str] = _id()
    deck_id: Mapped[str] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="running", nullable=False)
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimate: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = _created()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CostEntry(Base):
    __tablename__ = "cost_entry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(26), index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    at: Mapped[datetime] = _created()


class ModelCallCache(Base):
    __tablename__ = "model_call_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[Any] = mapped_column(JSON, nullable=False)
    usage: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created()


class FetchCache(Base):
    __tablename__ = "fetch_cache"
    url_normalized: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128))
    text_hash: Mapped[str | None] = mapped_column(String(64))
    robots_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fetched_at: Mapped[datetime] = _created()


class Calibration(Base):
    __tablename__ = "calibration"
    stage: Mapped[str] = mapped_column(String(32), primary_key=True)
    ratio_ema: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
