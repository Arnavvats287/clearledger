"""Protect exact provider labels and the paired development transport settings."""

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from accuracy_worker import DevelopmentWorker, Worker  # noqa: E402
from external_eval.accuracy_nli import (  # noqa: E402
    DecisionRow,
    exact_label_provider_schema,
)
from external_eval.gemini_http import MODEL, generation_request  # noqa: E402
from pydantic import ValidationError  # noqa: E402


def test_provider_constrains_only_final_label() -> None:
    schema = exact_label_provider_schema()
    answers = schema["properties"]["answers"]
    row = answers["items"]["properties"]
    assert row["predicted_label"]["enum"] == ["Entailment", "Contradiction", "NotMentioned"]
    assert "maxItems" not in answers and "maxItems" not in row["aliases"]
    assert "enum" not in row["aliases"]["items"] and "enum" not in row["relation"]


@pytest.mark.parametrize("bad", ["CONTRADICTION", "NOT_MENTIONED", "not-mentioned", "supports"])
def test_local_label_parser_does_not_relabel(bad: str) -> None:
    with pytest.raises(ValidationError, match="literal_error"):
        DecisionRow.model_validate(
            {
                "hypothesis_id": "H01",
                "predicted_label": bad,
                "aliases": [],
                "relation": "NONE",
                "contradiction_basis": "NONE",
            }
        )


def test_thinking_ablation_only_changes_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    def capture(_self: Worker, _operation: str, body: dict[str, Any]) -> dict[str, Any]:
        return body

    monkeypatch.setattr(Worker, "http", capture)
    worker = object.__new__(DevelopmentWorker)
    worker.selection = True
    worker.model = MODEL
    requests = []
    for thinking in ("MINIMAL", "LOW"):
        worker.thinking = thinking
        body = generation_request({"fixture": True}, "fixture", exact_label_provider_schema(), 4096)
        counted = worker.http(
            "countTokens", {"generateContentRequest": {"model": f"models/{MODEL}", **body}}
        )
        generated = worker.http("generateContent", body)
        assert (
            counted["generateContentRequest"]["generationConfig"] == generated["generationConfig"]
        )
        assert generated["generationConfig"]["thinkingConfig"].pop("thinkingLevel") == thinking
        requests.append(generated)
    assert requests[0] == requests[1]
