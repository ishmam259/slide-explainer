"""Every structured-output schema must be accepted by OpenAI strict mode (found in a live run)."""

from __future__ import annotations

import json

import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel

from slidex.llm import schemas

MODELS = [
    obj
    for obj in vars(schemas).values()
    if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == schemas.__name__
]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_no_oneof_in_strict_schema(model: type[BaseModel]) -> None:
    schema = json.dumps(to_strict_json_schema(model))
    assert '"oneOf"' not in schema, f"{model.__name__}: OpenAI rejects oneOf; use a plain union"


def test_blocks_still_parse_by_type() -> None:
    doc = schemas.SlideExplanation.model_validate(
        {
            "title": "Quorums",
            "blocks": [
                {"type": "slide_says", "text": "R + W > N", "citations": ["S5"]},
            ],
        }
    )
    assert type(doc.blocks[0]).__name__ == "SlideSaysBlock"
