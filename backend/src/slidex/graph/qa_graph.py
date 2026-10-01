"""Grounded Q&A and quizzes with a hint ladder (US4, FR-027–FR-029).

These are short request/response interactions, so they are plain async services rather than
a checkpointed graph; all state (threads, quiz progress, hint level) lives in SQLite, which
makes resuming trivial (FR-029).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import select

from slidex.api.deps import AppContext
from slidex.core.errors import SlidexError
from slidex.db.tables import QaThread, QaTurn, QuizItem, QuizSession, Slide, Source
from slidex.explain.evidence import passage_ref, slide_ref
from slidex.llm.prompts import load, untrusted
from slidex.llm.schemas import EvidenceRef, QaAnswer, QuizGrade, QuizQuestionSet
from slidex.retrieval.embed import embed_owners, embed_query
from slidex.retrieval.index import approved_usable_sources, collapsed_tree, search

DECLINE_BELOW = 0.2  # best evidence similarity below this → decline without calling the model
MAX_HINT = 3


@dataclass
class Evidence:
    refs: dict[str, EvidenceRef]
    text: str
    best_score: float


async def _ensure_slide_embeddings(
    ctx: AppContext, deck_id: str, run_id: str | None
) -> list[Slide]:
    with ctx.db.session() as s:
        slides = list(
            s.scalars(select(Slide).where(Slide.deck_id == deck_id).order_by(Slide.number))
        )
    items = []
    for sl in slides:
        ex = sl.extraction or {}
        meaning = (sl.interpretation or {}).get("meaning", "")
        items.append((sl.id, f"{ex.get('topic', '')}\n{ex.get('text', sl.native_text)}\n{meaning}"))
    await embed_owners(ctx, "slide", items, stage="qa", run_id=run_id)
    return slides


async def gather_evidence(
    ctx: AppContext,
    deck_id: str,
    query: str,
    run_id: str | None,
    slide_numbers: list[int] | None = None,
) -> Evidence:
    slides = await _ensure_slide_embeddings(ctx, deck_id, run_id)
    if slide_numbers:
        slides = [sl for sl in slides if sl.number in slide_numbers]
    qvec = np.asarray(await embed_query(ctx, query, run_id, "qa"))
    by_id = {sl.id: sl for sl in slides}
    hits = search(ctx.db, "slide", list(by_id), qvec, 4)
    refs: dict[str, EvidenceRef] = {}
    parts: list[str] = []
    best = max((h.score for h in hits), default=0.0)
    for h in hits:
        sl = by_id[h.owner_id]
        eid = f"S{sl.number}"
        refs[eid] = slide_ref(sl.number)
        meaning = (sl.interpretation or {}).get("meaning")
        parts.append(
            f"[{eid}] {(sl.extraction or {}).get('text', sl.native_text)}"
            + (f"\nInterpretation: {meaning}" if meaning else "")
        )
    source_ids = approved_usable_sources(ctx.db, deck_id)
    passages = collapsed_tree(ctx.db, source_ids, qvec, k=6, token_budget=2500)
    with ctx.db.session() as s:
        sources = {x.id: x for x in s.scalars(select(Source).where(Source.id.in_(source_ids)))}
    for i, p in enumerate(passages, start=1):
        eid = f"{'B' if p.owner_type == 'book_node' else 'W'}{i}"
        refs[eid] = passage_ref(eid, p, sources[p.source_id])
        parts.append(f"[{eid}] ({refs[eid].label})\n{untrusted(p.source_id, p.text)}")
        best = max(best, p.score)
    return Evidence(refs, "\n\n".join(parts), best)


def _refs(ids: list[str], ev: Evidence) -> list[dict[str, Any]]:
    return [ev.refs[i].model_dump(mode="json") for i in ids if i in ev.refs]


async def ask(ctx: AppContext, deck_id: str, question: str, thread_id: str | None) -> QaTurn:
    with ctx.db.session() as s:
        if thread_id is None or s.get(QaThread, thread_id) is None:
            thread = QaThread(deck_id=deck_id)
            s.add(thread)
            s.flush()
            thread_id = thread.id
        s.add(QaTurn(thread_id=thread_id, role="learner", text=question))
    ev = await gather_evidence(ctx, deck_id, question, None)
    if ev.best_score < DECLINE_BELOW or not ev.refs:
        answer = QaAnswer(
            declined=True,
            text="Your slides and the approved sources don't cover "
            "this. I can research it if you want.",
        )
    else:
        answer = await ctx.llm.parse(
            role="strong",
            stage="qa",
            prompt_version="qa_answer.v1",
            instructions=load("qa_answer.v1"),
            input_text=f"QUESTION: {question}\n\nEVIDENCE:\n{ev.text}",
            schema=QaAnswer,
        )
        cited = [c for c in answer.citations if c in ev.refs]
        if not answer.declined and not cited:  # constitution I: cite or decline
            answer = QaAnswer(
                declined=True,
                text="I couldn't ground an answer in your slides or "
                "approved sources. I can research it if you want.",
            )
        answer.citations = cited
    with ctx.db.session() as s:
        turn = QaTurn(
            thread_id=thread_id,
            role="assistant",
            text=answer.text,
            citations=_refs(answer.citations, ev),
            declined=answer.declined,
        )
        s.add(turn)
        s.flush()
        return turn


# ------------------------------------------------------------------ quiz


async def create_quiz(
    ctx: AppContext, deck_id: str, slide_from: int, slide_to: int, count: int
) -> str:
    if slide_to < slide_from:
        raise SlidexError("validation_error", "slide_to must be ≥ slide_from")
    numbers = list(range(slide_from, slide_to + 1))
    ev = await gather_evidence(
        ctx, deck_id, f"key ideas of slides {slide_from}-{slide_to}", None, slide_numbers=numbers
    )
    qs = await ctx.llm.parse(
        role="strong",
        stage="qa",
        prompt_version="quiz_generate.v1",
        instructions=load("quiz_generate.v1"),
        input_text=f"Write {count} questions about slides {slide_from}–{slide_to}.\n\n{ev.text}",
        schema=QuizQuestionSet,
    )
    with ctx.db.session() as s:
        session = QuizSession(deck_id=deck_id, slide_from=slide_from, slide_to=slide_to)
        s.add(session)
        s.flush()
        for i, q in enumerate(qs.questions[:count]):
            s.add(
                QuizItem(
                    session_id=session.id,
                    index=i,
                    question=q.question,
                    reference_answer=q.reference_answer,
                    evidence=_refs(q.evidence_ids, ev) or _refs(list(ev.refs)[:1], ev),
                )
            )
        return session.id


def quiz_state(ctx: AppContext, quiz_id: str) -> dict[str, Any]:
    with ctx.db.session() as s:
        session = s.get(QuizSession, quiz_id)
        if session is None:
            raise SlidexError("not_found", f"Quiz {quiz_id} not found")
        items = list(
            s.scalars(
                select(QuizItem).where(QuizItem.session_id == quiz_id).order_by(QuizItem.index)
            )
        )
    current = items[session.current_index] if session.current_index < len(items) else None
    correct = sum(1 for it in items if any(a["verdict"] == "correct" for a in it.attempts))
    answered = sum(1 for it in items if it.attempts)
    return {
        "id": session.id,
        "deck_id": session.deck_id,
        "slide_from": session.slide_from,
        "slide_to": session.slide_to,
        "status": session.status,
        "index": session.current_index,
        "total": len(items),
        "question": current.question if current else None,
        "hint_level": current.hint_level if current else 0,
        "score": {"correct": correct, "answered": answered},
    }


def _advance(s: Any, session: QuizSession, total: int) -> None:
    session.current_index += 1
    if session.current_index >= total:
        session.status = "completed"


async def answer_quiz(ctx: AppContext, quiz_id: str, answer: str) -> dict[str, Any]:
    with ctx.db.session() as s:
        session = s.get(QuizSession, quiz_id)
        if session is None:
            raise SlidexError("not_found", f"Quiz {quiz_id} not found")
        if session.status == "completed":
            raise SlidexError("invalid_state", "Quiz already completed.")
        item = s.scalars(
            select(QuizItem).where(
                QuizItem.session_id == quiz_id, QuizItem.index == session.current_index
            )
        ).one()
        level_requested = min(item.hint_level + 1, MAX_HINT)
    grade = await ctx.llm.parse(
        role="strong",
        stage="qa",
        prompt_version="quiz_grade.v1",
        instructions=load("quiz_grade.v1"),
        input_text=(
            f"QUESTION: {item.question}\nREFERENCE ANSWER: {item.reference_answer}\n"
            f"STUDENT ANSWER: {answer}\nHINT LEVEL: {min(level_requested, 2)}"
        ),
        schema=QuizGrade,
    )
    feedback: dict[str, Any] = {
        "verdict": grade.verdict,
        "misconception": grade.misconception,
        "hint": None,
        "pointer": None,
        "revealed_answer": None,
        "explanation": None,
        "citations": item.evidence,
    }
    with ctx.db.session() as s:
        session = s.get(QuizSession, quiz_id)
        it = s.get(QuizItem, item.id)
        assert session is not None and it is not None
        total = len(list(s.scalars(select(QuizItem.id).where(QuizItem.session_id == quiz_id))))
        if grade.verdict == "correct":
            it.attempts = [
                *it.attempts,
                {
                    "answer": answer,
                    "verdict": "correct",
                    "misconception": None,
                    "hint_level": it.hint_level,
                },
            ]
            feedback["explanation"] = it.reference_answer
            _advance(s, session, total)
        elif it.hint_level >= MAX_HINT:
            # ladder exhausted → reveal (FR-028)
            it.revealed = True
            it.attempts = [
                *it.attempts,
                {
                    "answer": answer,
                    "verdict": grade.verdict,
                    "misconception": grade.misconception,
                    "hint_level": it.hint_level,
                },
            ]
            feedback.update(verdict="revealed", revealed_answer=it.reference_answer)
            _advance(s, session, total)
        else:
            it.hint_level += 1
            it.attempts = [
                *it.attempts,
                {
                    "answer": answer,
                    "verdict": grade.verdict,
                    "misconception": grade.misconception,
                    "hint_level": it.hint_level,
                },
            ]
            if it.hint_level < MAX_HINT:
                feedback["hint"] = grade.hint
            else:
                feedback["pointer"] = it.evidence[0] if it.evidence else None
                feedback["hint"] = "Review this before trying again."
        feedback["hint_level"] = it.hint_level
    feedback["state"] = quiz_state(ctx, quiz_id)
    return feedback


def reveal_quiz(ctx: AppContext, quiz_id: str) -> dict[str, Any]:
    with ctx.db.session() as s:
        session = s.get(QuizSession, quiz_id)
        if session is None:
            raise SlidexError("not_found", f"Quiz {quiz_id} not found")
        if session.status == "completed":
            raise SlidexError("invalid_state", "Quiz already completed.")
        it = s.scalars(
            select(QuizItem).where(
                QuizItem.session_id == quiz_id, QuizItem.index == session.current_index
            )
        ).one()
        it.revealed = True
        total = len(list(s.scalars(select(QuizItem.id).where(QuizItem.session_id == quiz_id))))
        result = {
            "verdict": "revealed",
            "misconception": None,
            "hint": None,
            "pointer": None,
            "revealed_answer": it.reference_answer,
            "explanation": None,
            "citations": it.evidence,
            "hint_level": it.hint_level,
        }
        _advance(s, session, total)
    result["state"] = quiz_state(ctx, quiz_id)
    return result
