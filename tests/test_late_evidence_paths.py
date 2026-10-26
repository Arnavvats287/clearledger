"""Approved visible category only; no benchmark files or financial dataset fixtures."""

import sys
from pathlib import Path

import pytest
from test_chronological_evaluation import message
from test_imports import csv_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from application_eval_inputs import GROUPS, IMPORTS, Snapshot  # noqa: E402
from chronological_protocol import Stage, allowed  # noqa: E402

NAME = "app_visible/evidence_corpus/late_evidence/example.pdf"
RAW = b"application-owned protocol byte fixture"


def test_approved_late_evidence_pdf_path_and_payload_accepted():
    assert "late_evidence" in GROUPS
    assert allowed(NAME)
    stage = Stage(message(inputs={NAME: RAW}))
    assert stage.bytes[NAME] == RAW


def test_snapshot_uses_the_same_single_group_addition(tmp_path):
    (tmp_path / "imports").mkdir()
    for kind in IMPORTS:
        (tmp_path / f"imports/{kind}.csv").write_bytes(csv_bytes(kind))
    source = tmp_path / NAME
    source.parent.mkdir(parents=True)
    source.write_bytes(RAW)
    snapshot = Snapshot(tmp_path, "2026-01-19T12:00:00+05:30")
    assert snapshot.read(NAME) == RAW
    snapshot.verify()


@pytest.mark.parametrize(
    "name",
    [
        "app_visible/evidence_corpus/unsupported/example.pdf",
        "app_visible/evidence_corpus/late_evidence_other/example.pdf",
        "app_visible/evidence_corpus/late_evidence/nested/example.pdf",
        "app_visible/evidence_corpus/late_evidence/../example.pdf",
        "app_visible/evidence_corpus/late_evidence/.hidden.pdf",
        "app_visible/evidence_corpus/late_evidence/example.py",
        "app_visible/evidence_corpus/late_evidence/example\n.pdf",
        "/app_visible/evidence_corpus/late_evidence/example.pdf",
        "C:/app_visible/evidence_corpus/late_evidence/example.pdf",
        "app_visible\\evidence_corpus\\late_evidence\\example.pdf",
        "hidden_ground_truth/late_evidence/example.pdf",
    ],
)
def test_unknown_groups_and_unsafe_paths_still_rejected(name):
    assert not allowed(name)
    with pytest.raises(ValueError, match="INPUT_ALLOWLIST_OR_HASH"):
        Stage(message(inputs={name: RAW}))


@pytest.mark.parametrize("digest", [None, 7, "A" * 64, "a" * 63, "g" * 64, "0" * 64])
def test_invalid_digest_shape_or_mismatched_bytes_still_rejected(digest):
    request = message(inputs={NAME: RAW})
    request["manifest"][NAME] = digest
    expected = "INPUT_HASH_OR_SIZE" if digest == "0" * 64 else "INPUT_ALLOWLIST_OR_HASH"
    with pytest.raises(ValueError, match=expected):
        Stage(request)
