"""Q&A and quizzes (US4)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from slidex.api import convert
from slidex.api import schemas as S
from slidex.api.deps import AppContext, get_ctx
from slidex.core.errors import SlidexError
from slidex.db.tables import QaThread, QaTurn
from slidex.graph import qa_graph

router = APIRouter(tags=["learn"])
Ctx = Annotated[AppContext, Depends(get_ctx)]


async def _on_worker(ctx: AppContext, fn: Any) -> Any:
    return await asyncio.to_thread(ctx.worker.run_sync, fn)


@router.post(
    "/decks/{deck_id}/qa",
    operation_id="askQuestion",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE"}},
)
async def ask(deck_id: str, body: S.QuestionIn, ctx: Ctx) -> EventSourceResponse:
    turn = await _on_worker(ctx, lambda: qa_graph.ask(ctx, deck_id, body.question, body.thread_id))
    out = convert.qa_turn_out(turn)

    async def gen() -> AsyncIterator[dict[str, str]]:
        words = out.text.split(" ")
        for i in range(0, len(words), 8):  # stream the validated answer in small chunks
            yield {"event": "answer.delta", "data": " ".join(words[i : i + 8]) + " "}
        yield {
            "event": "answer.declined" if out.declined else "answer.done",
            "data": out.model_dump_json(),
        }

    return EventSourceResponse(gen())


@router.get("/decks/{deck_id}/qa/threads/{thread_id}", operation_id="getQaThread")
def get_thread(deck_id: str, thread_id: str, ctx: Ctx) -> S.QaThreadOut:
    with ctx.db.session() as s:
        thread = s.get(QaThread, thread_id)
        if thread is None or thread.deck_id != deck_id:
            raise SlidexError("not_found", "Thread not found")
        turns = list(
            s.scalars(
                select(QaTurn).where(QaTurn.thread_id == thread_id).order_by(QaTurn.created_at)
            )
        )
    return S.QaThreadOut(id=thread_id, turns=[convert.qa_turn_out(t) for t in turns])


def _feedback(raw: dict[str, Any]) -> S.QuizFeedback:
    return S.QuizFeedback(
        verdict=raw["verdict"],
        misconception=raw.get("misconception"),
        hint=raw.get("hint"),
        pointer=convert.evidence(raw["pointer"]) if raw.get("pointer") else None,
        revealed_answer=raw.get("revealed_answer"),
        explanation=raw.get("explanation"),
        citations=[convert.evidence(c) for c in raw.get("citations") or []],
        hint_level=raw["hint_level"],
        state=S.QuizState.model_validate(raw["state"]),
    )


@router.post("/decks/{deck_id}/quizzes", operation_id="createQuiz", status_code=201)
async def create_quiz(deck_id: str, body: S.QuizIn, ctx: Ctx) -> S.QuizState:
    quiz_id = await _on_worker(
        ctx, lambda: qa_graph.create_quiz(ctx, deck_id, body.slide_from, body.slide_to, body.count)
    )
    return S.QuizState.model_validate(qa_graph.quiz_state(ctx, quiz_id))


@router.get("/quizzes/{quiz_id}", operation_id="getQuiz")
def get_quiz(quiz_id: str, ctx: Ctx) -> S.QuizState:
    return S.QuizState.model_validate(qa_graph.quiz_state(ctx, quiz_id))


@router.post("/quizzes/{quiz_id}/answer", operation_id="answerQuiz")
async def answer(quiz_id: str, body: S.AnswerIn, ctx: Ctx) -> S.QuizFeedback:
    return _feedback(await _on_worker(ctx, lambda: qa_graph.answer_quiz(ctx, quiz_id, body.answer)))


@router.post("/quizzes/{quiz_id}/reveal", operation_id="revealQuizAnswer")
def reveal(quiz_id: str, ctx: Ctx) -> S.QuizFeedback:
    return _feedback(qa_graph.reveal_quiz(ctx, quiz_id))
