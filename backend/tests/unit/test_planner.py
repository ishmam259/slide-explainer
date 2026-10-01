import numpy as np

from slidex.explain.planner import SlidePlanInput, plan_document


def _slides() -> list[SlidePlanInput]:
    return [
        SlidePlanInput(1, ["agenda"], "Intro", is_divider=True),
        SlidePlanInput(3, ["quorum", "replication"], "Replication"),
        SlidePlanInput(7, ["quorum", "latency"], "Replication"),
        SlidePlanInput(12, ["Quorum"], "Consistency"),
    ]


def test_concept_explained_once_then_referred_back() -> None:
    plan = plan_document(_slides())
    assert plan.order == [3, 7, 12]  # divider skipped
    assert "quorum" in plan.slides[3].explain_fully
    assert plan.slides[7].refer_back == {"quorum": 3}
    assert plan.slides[12].refer_back == {"Quorum": 3}  # case-insensitive match
    assert "latency" in plan.slides[7].explain_fully


def test_synonyms_merged_by_similarity() -> None:
    v = np.array([1.0, 0.0])
    slides = [SlidePlanInput(1, ["read quorum"], "A"), SlidePlanInput(2, ["quorum read"], "A")]
    plan = plan_document(slides, concept_vectors={"read quorum": v, "quorum read": v * 0.99})
    assert plan.slides[2].refer_back == {"quorum read": 1}


def test_by_topic_groups_keep_slide_order() -> None:
    plan = plan_document(_slides(), organization="by_topic")
    assert plan.sections == [("Replication", [3, 7]), ("Consistency", [12])]


def test_slide_range_respected() -> None:
    plan = plan_document(_slides(), slide_range=(7, 12))
    assert plan.order == [7, 12]
    assert "quorum" in plan.slides[7].explain_fully  # first occurrence inside the range
