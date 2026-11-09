"""Check fresh selection, source-only projection and the two-seal scoring gate."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import external_phase3b_score  # noqa: E402
from external_phase3b import contract_texts, select_ids, source_ids  # noqa: E402


def test_source_projection_reads_only_requested_document_fields(tmp_path: Path) -> None:
    path = tmp_path / "public-split.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": 1,
                        "text": 'line one\n"id": 2,',
                        "annotation_sets": [{"id": 100, "text": "gold"}],
                    },
                    {"id": 3, "text": "second", "annotation_sets": []},
                ]
            },
            indent=2,
        ),
        encoding="utf8",
    )
    assert source_ids(path) == ["1", "3"]
    assert contract_texts(path, {"1"}) == {"1": 'line one\n"id": 2,'}


def test_selection_is_deterministic_with_no_replacement() -> None:
    ids = [str(i) for i in range(10)]
    selected = select_ids("contract-nli", ids, {"2", "3"}, 8)
    assert selected == select_ids("contract-nli", list(reversed(ids)), {"2", "3"}, 8)
    assert set(selected) == set(ids) - {"2", "3"}
    with pytest.raises(ValueError, match="INSUFFICIENT_UNUSED_SOURCE_IDS"):
        select_ids("contract-nli", ids, {"2", "3"}, 9)


def test_scorer_needs_both_prediction_seals_before_gold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unsealed(_root: Path) -> None:
        raise ValueError("PREDICTION_SEAL_IDENTITY_MISMATCH")

    def reject_gold(*_args: object) -> None:
        pytest.fail("Gold reader ran before both seals")

    monkeypatch.setattr(external_phase3b_score, "sealed_predictions", unsealed)
    monkeypatch.setattr(external_phase3b_score, "contract_gold", reject_gold)
    monkeypatch.setattr(external_phase3b_score, "docile_gold", reject_gold)
    with pytest.raises(ValueError, match="PREDICTION_SEAL_IDENTITY_MISMATCH"):
        external_phase3b_score.score(tmp_path, tmp_path / "gold")
