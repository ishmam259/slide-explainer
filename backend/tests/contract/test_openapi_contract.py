"""The running app must implement the API contract (Constitution IV).

Contract: specs/001-slide-explainer/contracts/openapi.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from slidex.main import create_app

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-slide-explainer"
    / "contracts"
    / "openapi.yaml"
)
METHODS = ("get", "post", "put", "patch", "delete")


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    app_spec = create_app().openapi()
    return contract, app_spec


CONTRACT_SPEC, APP_SPEC = _load()
OPERATIONS = [
    (path, method)
    for path, item in CONTRACT_SPEC["paths"].items()
    for method in METHODS
    if method in item
]


@pytest.mark.parametrize(
    ("path", "method"), OPERATIONS, ids=[f"{m.upper()} {p}" for p, m in OPERATIONS]
)
def test_operation_exists_with_success_status(path: str, method: str) -> None:
    app_item = APP_SPEC["paths"].get(path)
    assert app_item is not None and method in app_item, f"{method.upper()} {path} not implemented"
    want = {c for c in CONTRACT_SPEC["paths"][path][method]["responses"] if c.startswith("2")}
    have = {c for c in app_item[method]["responses"] if c.startswith("2")}
    assert want <= have, f"{method.upper()} {path}: contract {want}, app {have}"


def test_operation_ids_match() -> None:
    for path, method in OPERATIONS:
        want = CONTRACT_SPEC["paths"][path][method].get("operationId")
        have = APP_SPEC["paths"][path][method].get("operationId")
        assert want == have, f"{method.upper()} {path}: operationId {have!r} != {want!r}"


@pytest.mark.parametrize(
    "name",
    [
        "Problem",
        "Health",
        "DeckSummary",
        "DeckDetail",
        "DeckContext",
        "Slide",
        "Visual",
        "Topic",
        "Source",
        "DeckSource",
        "SourceList",
        "EvidenceRef",
        "Disagreement",
        "ExplanationDocument",
        "RunEstimate",
        "StageEstimate",
        "Run",
        "QaTurn",
        "QuizState",
        "QuizFeedback",
    ],
)
def test_response_schemas_present(name: str) -> None:
    assert name in CONTRACT_SPEC["components"]["schemas"]
    assert name in APP_SPEC["components"]["schemas"], f"schema {name} missing from app"


def test_problem_codes_match() -> None:
    from slidex.core.errors import PROBLEM_CODES

    want = set(CONTRACT_SPEC["components"]["schemas"]["Problem"]["properties"]["code"]["enum"])
    assert set(PROBLEM_CODES) == want
