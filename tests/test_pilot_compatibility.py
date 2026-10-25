"""Minimal compatibility harness fixtures; no pilot data or answers in Git."""

import hashlib
import json
from zipfile import ZipFile

import pytest
from test_pilot_harness import tiny_archive

from scripts.pilot_compat_score import email_body_location, evaluate_compat
from scripts.pilot_package import (
    VisibleSplit,
    copy_visible,
    portable_validator_source,
    verify_archive,
)


def test_successor_root_preserves_predecessor_and_manifest_checks(tmp_path):
    original = tiny_archive(tmp_path)
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    successor = tmp_path / "successor.zip"
    with ZipFile(original) as old, ZipFile(successor, "w") as new:
        for name in old.namelist():
            new.writestr(
                name.replace("clearledger_pilot_v1/", "clearledger_pilot_v1_1/"), old.read(name)
            )
    assert verify_archive(successor)["archive_root"] == "clearledger_pilot_v1_1"
    assert verify_archive(original)["archive_root"] == "clearledger_pilot_v1"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("root", ["other", "clearledger_pilot_v2"])
def test_unknown_roots_remain_rejected(tmp_path, root):
    path = tmp_path / "bad.zip"
    with ZipFile(path, "w") as zipped:
        zipped.writestr(root + "/MANIFEST.json", "{}")
    with pytest.raises(ValueError, match="Unsupported archive root"):
        verify_archive(path)


def test_portable_validator_changes_only_one_path_expression_and_no_assertions():
    original = "source={str(p.relative_to(root)):value}\nassert manifest==source\n"
    adapted = portable_validator_source(original)
    assert adapted == "source={p.relative_to(root).as_posix():value}\nassert manifest==source\n"
    assert original == "source={str(p.relative_to(root)):value}\nassert manifest==source\n"
    for unsupported in ("no expression", original + original):
        with pytest.raises(ValueError):
            portable_validator_source(unsupported)


def test_explicit_supplement_copy_does_not_expose_hidden_targets(tmp_path):
    package = tmp_path / "package"
    split = package / "dev"
    for kind in ("customers", "payer-aliases", "invoices", "bank-transactions"):
        path = split / f"imports/{kind}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("h\nx\n")
    corpus = split / "app_visible/evidence_corpus"
    corpus.mkdir(parents=True)
    (corpus / "evidence_inventory.jsonl").write_text("")
    (split / "app_visible/operational_events.jsonl").write_text("")
    supplement = split / "app_visible/compatibility_structured_remittances/a.json"
    supplement.parent.mkdir()
    supplement.write_text("{}")
    metadata = {"documents": [{"source_path": "compatibility_structured_remittances/a.json"}]}
    (split / "app_visible/COMPATIBILITY_ADDITIONS.json").write_text(json.dumps(metadata))
    hidden = split / "hidden_ground_truth"
    hidden.mkdir()
    (hidden / "compatibility_correlation_targets.json").write_text('"ANSWER_CANARY"')
    target = tmp_path / "application"
    visible = copy_visible(package, "dev", target)
    assert visible.read("app_visible/compatibility_structured_remittances/a.json") == b"{}"
    assert not any(b"ANSWER_CANARY" in p.read_bytes() for p in target.rglob("*") if p.is_file())
    with pytest.raises(ValueError):
        VisibleSplit(split).read("hidden_ground_truth/compatibility_correlation_targets.json")


def test_email_diagnostics_measure_unicode_bytes_in_actual_output():
    prefix = "Subject: \u20b9\n\n"
    body = "Invoice n\n"
    result = email_body_location(prefix + body, body)
    assert result == {
        "body_char_start": len(prefix),
        "body_byte_start": len(prefix.encode()),
        "prefix_chars": len(prefix),
        "body_exact": True,
    }
    assert email_body_location(body + body, body) is None
    assert email_body_location("unrelated", body) is None
    assert email_body_location("anything", "") is None


def scoring_fixture(tmp_path):
    root = tmp_path / "package"
    records = {
        "bank-transactions": [
            {"id": "b", "external_transaction_id": "t", "source_system": "s", "account_ref": "a"}
        ],
        "receipts": [{"id": "r", "bank_transaction_id": "b"}],
    }
    target = {
        "synthetic_addition_file": "p.json",
        "target_receipt": {
            "external_transaction_id": "t",
            "source_system": "s",
            "account_ref": "a",
        },
        "invoice_references_stated_by_synthetic_sender": [],
    }
    hidden = root / "dev/hidden_ground_truth"
    hidden.mkdir(parents=True)
    (hidden / "ground_truth_cases.jsonl").write_text("")
    (hidden / "compatibility_correlation_targets.json").write_text(
        json.dumps({"targets": [target, {"synthetic_addition_file": "n.json"}]})
    )

    def entry(link):
        return {
            "extraction": {
                "route": "DETERMINISTIC",
                "status": "SUCCEEDED",
                "result": {"invoice_references": []},
            },
            "verified_spans": 1,
            "unattested": {"status": "CANDIDATES" if link else "UNRESOLVED"},
            "simulated_utr_attested": {
                "status": "LINKED" if link else "UNRESOLVED",
                "receipt_id": "r" if link else None,
                "result": {"reason": "test"},
            },
            "missing_version_probed": link,
            "stale_version_probed": link,
        }

    observations = {
        "dev": {
            "records": records,
            "documents": {},
            "financial_mutations": 0,
            "compatibility_structured_remittances": {"p.json": entry(True), "n.json": entry(False)},
        }
    }
    return root, observations


def test_answer_only_scoring_distinguishes_attested_links_and_negative_controls(tmp_path):
    root, observations = scoring_fixture(tmp_path)
    summary, _ = evaluate_compat(root, observations)
    assert summary["dev"]["correct_positive_links"] == 1
    assert summary["dev"]["correct_negative_abstentions"] == 1
    assert summary["dev"]["false_links"] == 0 and summary["safety_blockers"] == []


def test_old_email_span_is_reported_incompatible_without_rewriting_it(tmp_path):
    root, observations = scoring_fixture(tmp_path)
    prefix = "Subject: x\n\n"
    body = "ab\n"
    corpus = root / "dev/app_visible/evidence_corpus"
    corpus.mkdir(parents=True)
    (corpus / "e.canonical.txt").write_text(body)
    observations["dev"]["documents"]["e"] = {
        "inventory": {
            "source_path": "e.eml",
            "canonical_text_path": "evidence_corpus/e.canonical.txt",
        },
        "canonical": {"pages": [prefix + body]},
    }
    pointer = {"document_id": "e", "page_number": 1, "char_span": [0, 2], "exact_quote": "ab"}
    path = root / "dev/hidden_ground_truth/ground_truth_cases.jsonl"
    raw = json.dumps({"evidence_pointers": [pointer]})
    path.write_text(raw)
    summary, _ = evaluate_compat(root, observations)
    email = summary["dev"]["legacy_citation_formats"]["eml"]
    assert email["total"] == 1 and email["direct"] == 0
    assert email["measured_delta_chars"] == {len(prefix): 1}
    assert path.read_text() == raw


@pytest.mark.parametrize("source", ["p.json", "n.json"])
def test_wrong_or_negative_control_links_are_safety_blockers(tmp_path, source):
    root, observations = scoring_fixture(tmp_path)
    bad = observations["dev"]["compatibility_structured_remittances"][source][
        "simulated_utr_attested"
    ]
    bad.update(status="LINKED", receipt_id="wrong")
    summary, _ = evaluate_compat(root, observations)
    assert summary["dev"]["false_links"] == 1 and summary["safety_blockers"]
