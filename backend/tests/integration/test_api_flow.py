"""Full flow through the HTTP API, exactly as the frontend uses it (fake LLM, mocked web)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pymupdf
import pytest
import respx
from fastapi.testclient import TestClient

from slidex.core.config import get_settings
from slidex.main import create_app
from slidex.research import fetch
from tests.integration.test_agent_pipeline import web  # noqa: F401 — reuse the web mocks


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def _public(url: str) -> None:
        return None

    monkeypatch.setattr(fetch, "assert_public", _public)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c


def _pdf(path: Path) -> Path:
    doc = pymupdf.open()
    for text in [
        "Replication in distributed databases keeps copies of data on several replica nodes",
        "Quorum: R + W > N",
        "Quorum reads and writes guarantee that every read overlaps the latest successful write",
    ]:
        doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    return path


def _wait_status(c: TestClient, deck_id: str, want: str, timeout: float = 60) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        deck = c.get(f"/decks/{deck_id}").json()
        if deck["status"] == want:
            return deck
        assert deck["status"] != "failed", deck.get("error")
        time.sleep(0.1)
    raise AssertionError(f"deck never reached {want}: {deck['status']}")


def test_api_end_to_end(client: TestClient, web: respx.MockRouter, tmp_path: Path) -> None:  # noqa: F811
    c = client
    assert c.get("/health").json()["api_key_configured"] is True

    # Upload a PDF deck with context → extraction starts automatically
    with _pdf(tmp_path / "lecture.pdf").open("rb") as fh:
        r = c.post(
            "/decks",
            files={"files": ("lecture.pdf", fh, "application/pdf")},
            data={
                "context": json.dumps({"course": "Distributed Systems", "level": "intermediate"})
            },
        )
    assert r.status_code == 201, r.text
    deck_id = r.json()["id"]
    deck = _wait_status(c, deck_id, "awaiting_research_confirm")
    assert deck["clarity_counts"]["vague"] == 1

    slides = c.get(f"/decks/{deck_id}/slides").json()
    assert [s["number"] for s in slides] == [1, 2, 3]
    assert slides[0]["image_url"].startswith("/api/files/")
    vague = next(s for s in slides if s["clarity"] == "vague")
    hinted = c.put(
        f"/decks/{deck_id}/slides/{vague['number']}/hint",
        json={"hint": "This is the quorum overlap condition"},
    ).json()
    assert hinted["learner_hint"] and hinted["interpretation"]["confidence"] >= 0.8

    # Estimate, then confirm research
    est = c.get(f"/decks/{deck_id}/estimate", params={"stage": "research"}).json()
    assert est["total_usd"] >= 0 and est["stages"]
    assert c.post(f"/decks/{deck_id}/research", json={"confirm": True}).status_code == 202
    _wait_status(c, deck_id, "awaiting_source_approval")
    sources = c.get(f"/decks/{deck_id}/sources").json()
    titles = [s["source"]["title"] for t in sources["by_topic"] for s in t["sources"]]
    assert titles and not any("Helpful" in t for t in titles)  # injection page excluded
    assert sources["further_reading"]  # paywalled page

    # Approve sources → ready; generate a markdown document and download it
    assert c.post(f"/decks/{deck_id}/sources/approve").status_code == 202
    _wait_status(c, deck_id, "ready")
    doc = c.post(
        f"/decks/{deck_id}/documents", json={"organization": "by_slide", "formats": ["md"]}
    ).json()
    end = time.monotonic() + 60
    while doc["status"] not in ("ready", "failed") and time.monotonic() < end:
        time.sleep(0.1)
        doc = c.get(f"/documents/{doc['id']}").json()
    assert doc["status"] == "ready", doc
    dl = c.get(f"/documents/{doc['id']}/download/md")
    assert dl.status_code == 200 and dl.headers["content-type"] == "application/zip"

    # Q&A over SSE, then a quiz
    with c.stream(
        "POST", f"/decks/{deck_id}/qa", json={"question": "How do quorum reads work?"}
    ) as r:
        body = "".join(r.iter_text())
    assert "event: answer.done" in body
    quiz = c.post(f"/decks/{deck_id}/quizzes", json={"slide_from": 1, "slide_to": 3, "count": 2})
    assert quiz.status_code == 201 and quiz.json()["question"]
    fb = c.post(f"/quizzes/{quiz.json()['id']}/answer", json={"answer": "no idea"}).json()
    assert fb["hint_level"] == 1 and fb["revealed_answer"] is None

    # Errors are problem+json
    r = c.post(f"/decks/{deck_id}/research", json={"confirm": True})
    assert r.status_code == 409 and r.json()["code"] == "invalid_state"
