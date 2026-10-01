from slidex.explain.validate import find_filler, strip_filler, validate_blocks
from slidex.llm.schemas import (
    ExplanationBlock,
    ReconstructedBlock,
    ReferBackBlock,
    SlideSaysBlock,
)

KNOWN = {"S3", "W1", "B1"}


def test_unknown_ids_retried_first_then_dropped() -> None:
    bad = ExplanationBlock(markdown="x", citations=["W9"])
    first = validate_blocks(
        [bad], known_evidence=KNOWN, unusable_evidence=set(), slide_is_vague=False, first_pass=True
    )
    assert first.retry == [bad] and not first.kept
    second = validate_blocks(
        [bad], known_evidence=KNOWN, unusable_evidence=set(), slide_is_vague=False, first_pass=False
    )
    assert second.dropped and second.dropped[0][1] == "cites unknown evidence"


def test_refer_back_needs_no_citation() -> None:
    res = validate_blocks(
        [ReferBackBlock(concept="quorum", slide=3)],
        known_evidence=KNOWN,
        unusable_evidence=set(),
        slide_is_vague=False,
        first_pass=True,
    )
    assert len(res.kept) == 1


def test_reconstructed_only_on_vague_slides() -> None:
    block = ReconstructedBlock(markdown="m", confidence=0.6, citations=["W1"])
    clear = validate_blocks(
        [block],
        known_evidence=KNOWN,
        unusable_evidence=set(),
        slide_is_vague=False,
        first_pass=True,
    )
    vague = validate_blocks(
        [block], known_evidence=KNOWN, unusable_evidence=set(), slide_is_vague=True, first_pass=True
    )
    assert clear.dropped and not clear.kept
    assert vague.kept == [block]


def test_unusable_sources_rejected() -> None:
    block = ExplanationBlock(markdown="m", citations=["W1"])
    res = validate_blocks(
        [block],
        known_evidence=KNOWN,
        unusable_evidence={"W1"},
        slide_is_vague=False,
        first_pass=True,
    )
    assert res.dropped[0][1] == "cites a source that is not usable"


def test_filler_detected_and_stripped() -> None:
    text = "In this slide we will learn quorums. A quorum is a majority. Let's dive in."
    assert len(find_filler(text)) == 2
    assert strip_filler(text) == "A quorum is a majority."
    block = SlideSaysBlock(text=text, citations=["S3"])
    res = validate_blocks(
        [block],
        known_evidence=KNOWN,
        unusable_evidence=set(),
        slide_is_vague=False,
        first_pass=True,
    )
    assert res.kept == [block] and res.filler
