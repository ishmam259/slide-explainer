"""Deterministic fake model behaviour per prompt (used when SLIDEX_FAKE_LLM=1 and in tests).

Simple heuristics that respect each prompt's contract, so the full pipeline can run offline.
"""

from __future__ import annotations

import re
from collections import OrderedDict

from pydantic import BaseModel

from slidex.llm.fake import FakeRequest, register_handler
from slidex.llm.schemas import (
    ClusterSummary,
    DisagreementFinding,
    DisagreementItem,
    ExplanationBlock,
    FillerCheck,
    Position,
    QaAnswer,
    QueryPlan,
    QuizGrade,
    QuizQuestion,
    QuizQuestionSet,
    ReconstructedBlock,
    SafetyVerdict,
    SlideExplanation,
    SlideExtraction,
    SlideInterpretation,
    SlideSaysBlock,
    SourceRanking,
    TopicConsolidation,
    TopicItem,
)

_IDS = re.compile(r"^\[([SBWFD]\d+)\]", re.MULTILINE)
_WORDS = re.compile(r"[A-Za-z][A-Za-z\-]{3,}")
_DIVIDERS = ("questions?", "thank you", "agenda", "outline")


def _section(text: str, header: str) -> str:
    m = re.search(re.escape(header) + r"\n(.*?)(?:\n\n|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


@register_handler("slide_extract.v1")
def _extract(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    body = _section(req.input_text, "Machine-extracted slide text:")
    if body == "(none)":
        body = _section(req.input_text, "OCR text (may contain errors):")
    words = _WORDS.findall(body)
    first = body.splitlines()[0].strip() if body else ""
    if body.lower().strip() in _DIVIDERS or not words:
        clarity = "divider" if body.lower().strip() in _DIVIDERS else "unreadable"
    else:
        clarity = "vague" if len(body.split()) < 8 else "clear"
    concepts = list(OrderedDict.fromkeys(w.lower() for w in words if len(w) > 4))[:3] or [
        first or "slide"
    ]
    return SlideExtraction(
        title=first or None,
        text=body,
        topic=(first or "untitled")[:60],
        concepts=concepts,
        clarity=clarity,
    )


@register_handler("slide_interpret.v1")
def _interpret(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    hinted = "LEARNER HINT:" in req.input_text
    target = re.search(r"TARGET slide (\d+)", req.input_text)
    unreadable = "(unreadable)" in req.input_text
    confidence = 0.85 if hinted else (0.3 if unreadable else 0.7)
    text = _section(req.input_text, "TARGET slide " + (target.group(1) if target else "") + " ")
    return SlideInterpretation(
        meaning=f"Likely meaning of slide {target.group(1) if target else '?'}: {text[:300]}",
        confidence=confidence,
        rationale="Inferred from neighbouring slides.",
    )


@register_handler("topics_consolidate.v1")
def _topics(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    groups: OrderedDict[str, list[int]] = OrderedDict()
    for m in re.finditer(r"^- (\d+): topic=([^;]+);", req.input_text, re.MULTILINE):
        groups.setdefault(m.group(2).strip(), []).append(int(m.group(1)))
    items = [TopicItem(name=k, slide_numbers=v) for k, v in groups.items()] or [
        TopicItem(name="General", slide_numbers=[1])
    ]
    return TopicConsolidation(topics=items[:15])


@register_handler("plan_queries.v1")
def _queries(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    topic = re.search(r"Topic: (.+)", req.input_text)
    name = topic.group(1).strip() if topic else "topic"
    return QueryPlan(queries=[f"{name} lecture notes", f"{name} documentation"])


@register_handler("safety.v1")
def _safety(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    t = req.input_text.lower()
    if "buy now" in t or "casino" in t:
        return SafetyVerdict(verdict="spam", reason="Advertising content.")
    if "subscribe to continue" in t:
        return SafetyVerdict(verdict="paywall", reason="Subscription required.")
    return SafetyVerdict(verdict="ok", reason="Educational content.")


@register_handler("rank.v1")
def _rank(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    t = req.input_text.lower()
    edu = any(d in t for d in (".edu", "openstax", "libretexts", "docs."))
    return SourceRanking(
        relevance=0.85,
        authority=0.9 if edu else 0.6,
        kind="lecture_notes" if edu else "article",
        reason="Explains the same concept as the slides.",
    )


@register_handler("disagree.v1")
def _disagree(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    ids = _IDS.findall(req.input_text)
    if "DISAGREE" not in req.input_text or len(ids) < 2:
        return DisagreementFinding(disagreements=[])
    slide_ids = [i for i in ids if i.startswith("S")]
    web_ids = [i for i in ids if i.startswith("W")]
    if not slide_ids or not web_ids:
        return DisagreementFinding(disagreements=[])
    return DisagreementFinding(
        disagreements=[
            DisagreementItem(
                claim="Conflicting statement",
                involves_slide=int(slide_ids[0][1:]),
                positions=[
                    Position(statement="Slide claim", evidence_ids=[slide_ids[0]]),
                    Position(statement="Source claim", evidence_ids=[web_ids[0]]),
                ],
                assessment="The source is better supported.",
            )
        ]
    )


@register_handler("raptor_summary.v1")
def _summary(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    text = re.sub(r"</?untrusted_source[^>]*>", " ", req.input_text)
    return ClusterSummary(summary=" ".join(text.split())[:600], key_terms=[])


@register_handler("slide_explain.v1")
def _explain(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    ids = list(OrderedDict.fromkeys(_IDS.findall(req.input_text)))
    slide = next((i for i in ids if i.startswith("S")), "S1")
    support = [i for i in ids if not i.startswith("D")] or [slide]
    num = re.search(r"SLIDE (\d+)", req.input_text)
    blocks: list[object] = [SlideSaysBlock(text="What the slide states.", citations=[slide])]
    if "— VAGUE" in req.input_text:
        conf = re.search(r"Interpretation \(confidence ([0-9.]+)\)", req.input_text)
        blocks.append(
            ReconstructedBlock(
                markdown="Reconstructed explanation from sources.",
                confidence=float(conf.group(1)) if conf else 0.5,
                citations=support,
            )
        )
    blocks.append(
        ExplanationBlock(markdown="Detailed explanation of each point.", citations=support)
    )
    return SlideExplanation(title=f"Slide {num.group(1) if num else ''}".strip(), blocks=blocks)


@register_handler("filler_check.v1")
def _filler(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    return FillerCheck(has_filler=False)


@register_handler("qa_answer.v1")
def _qa(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    ids = list(OrderedDict.fromkeys(_IDS.findall(req.input_text)))
    return QaAnswer(
        declined=False, text="Answer grounded in the cited evidence.", citations=ids[:2]
    )


@register_handler("quiz_generate.v1")
def _quiz(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    count = int(m.group(1)) if (m := re.search(r"Write (\d+) questions", req.input_text)) else 3
    ids = list(OrderedDict.fromkeys(_IDS.findall(req.input_text))) or ["S1"]
    return QuizQuestionSet(
        questions=[
            QuizQuestion(
                question=f"Question {i + 1}: why does this work?",
                reference_answer="because replicas agree on a quorum",
                evidence_ids=[ids[i % len(ids)]],
            )
            for i in range(count)
        ]
    )


@register_handler("quiz_grade.v1")
def _grade(req: FakeRequest, _: type[BaseModel]) -> BaseModel:
    ref = set(
        _WORDS.findall(
            (
                _section(req.input_text, "REFERENCE ANSWER:")
                or re.search(r"REFERENCE ANSWER: (.*)", req.input_text).group(1)
            ).lower()
        )
    )
    ans_m = re.search(r"STUDENT ANSWER: (.*)", req.input_text)
    ans = set(_WORDS.findall((ans_m.group(1) if ans_m else "").lower()))
    overlap = len(ref & ans) / max(len(ref), 1)
    level = int(m.group(1)) if (m := re.search(r"HINT LEVEL: (\d)", req.input_text)) else 1
    if overlap >= 0.5:
        return QuizGrade(verdict="correct")
    return QuizGrade(
        verdict="incorrect",
        misconception="Confuses the mechanism.",
        hint=f"Hint level {level}: think about what the replicas must agree on.",
    )
