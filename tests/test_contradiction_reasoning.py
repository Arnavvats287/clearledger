"""Focused tests for the additive decision adapters and unchanged evidence gate."""

import sys
from pathlib import Path

import pytest

from clearledger.source_semantics import semantic_source
from clearledger.source_spans import text_source

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from external_eval.accuracy_nli import exact_label_provider_schema, packet, validate  # noqa: E402
from external_eval.contradiction import project, raw_label, schema  # noqa: E402


@pytest.mark.parametrize(
    ("support", "conflict", "label"),
    [
        (True, False, "Entailment"),
        (False, True, "Contradiction"),
        (False, False, "NotMentioned"),
    ],
)
def test_binary_truth_table(support: bool, conflict: bool, label: str) -> None:
    row = {
        "hypothesis_id": "H01",
        "support_present": support,
        "explicit_conflict_present": conflict,
        "aliases": [],
    }
    assert raw_label(row, "binary") == label
    assert project(row, "binary")["predicted_label"] == label


def test_binary_rejects_conflicting_or_string_flags() -> None:
    row = {
        "hypothesis_id": "H01",
        "support_present": True,
        "explicit_conflict_present": True,
        "aliases": ["E01"],
    }
    assert raw_label(row, "binary") is None
    with pytest.raises(ValueError, match="INVALID_CONFLICT"):
        project(row, "binary")
    with pytest.raises(ValueError, match="bool_type"):
        project({**row, "support_present": "false"}, "binary")


@pytest.mark.parametrize("label", ["Entailment", "Contradiction", "NotMentioned"])
def test_roles_rejects_missing_required_role_or_incompatible_roles(label: str) -> None:
    row = {
        "hypothesis_id": "H01",
        "predicted_label": label,
        "support_evidence": ["E01"] if label == "NotMentioned" else [],
        "conflict_evidence": [],
    }
    assert raw_label(row, "roles") == label
    with pytest.raises(ValueError, match="LABEL_EVIDENCE_ROLE_MISMATCH"):
        project(row, "roles")


def test_projection_cannot_bypass_reference_validation() -> None:
    src = semantic_source(text_source("fixture", ["The recipient may not distribute copies."]))
    p = packet(
        src,
        [{"hypothesis_id": "H01", "text": "The recipient may distribute copies."}],
        request="fixture",
    )
    row = {
        "hypothesis_id": "H01",
        "predicted_label": "Contradiction",
        "support_evidence": [],
        "conflict_evidence": ["E999"],
    }
    assert validate({"answers": [project(row, "roles")]}, p)[0].status == "INVALID_ALIAS"
    row["conflict_evidence"] = [p.registry.bindings[0].alias]
    assert validate({"answers": [project(row, "roles")]}, p)[0].status == "VALID_CONTRADICTION"


def test_provider_schemas_use_only_needed_formulation_fields() -> None:
    assert schema("rubric") == schema("few-shot") == exact_label_provider_schema()
    binary = schema("binary")["properties"]["answers"]["items"]["properties"]
    assert binary["explicit_conflict_present"] == {"type": "boolean"}
    assert "predicted_label" not in binary
    roles = schema("roles")["properties"]["answers"]["items"]["properties"]
    assert roles["predicted_label"]["enum"] == ["Entailment", "Contradiction", "NotMentioned"]
    assert all("maxItems" not in roles[k] for k in ("support_evidence", "conflict_evidence"))
