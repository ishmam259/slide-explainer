"""Section titles don't repeat the slide number; citation lines don't repeat a source."""

from __future__ import annotations

import pytest

from slidex.explain.assemble import _section_title
from slidex.llm.schemas import EvidenceRef
from slidex.render import cited


@pytest.mark.parametrize(
    ("n", "title", "want"),
    [
        (2, "Slide 2 · Why replicate?", "Slide 2: Why replicate?"),
        (15, "Slide 15: CAP theorem", "Slide 15: CAP theorem"),
        (11, "Replication lag (Slide 11)", "Slide 11: Replication lag"),
        (4, "Slide 4", "Slide 4"),
        (1, "Slide 12 recap", "Slide 1: Slide 12 recap"),
        (6, "Quorums", "Slide 6: Quorums"),
    ],
)
def test_section_title(n: int, title: str, want: str) -> None:
    assert _section_title(n, title) == want


def test_cited_drops_repeated_labels() -> None:
    ref = EvidenceRef.model_validate
    ev = {
        "W1": ref(
            {
                "evidence_id": "W1",
                "kind": "web",
                "label": "MIT 6.033 notes",
                "url": "https://a/x",
            }
        ),
        "W2": ref(
            {
                "evidence_id": "W2",
                "kind": "web",
                "label": "MIT 6.033 notes",
                "url": "https://a/x",
            }
        ),
        "S3": ref({"evidence_id": "S3", "kind": "slide", "label": "Slide 3"}),
    }
    assert [r.label for r in cited(["W1", "S3", "W2", "missing"], ev)] == [
        "MIT 6.033 notes",
        "Slide 3",
    ]
