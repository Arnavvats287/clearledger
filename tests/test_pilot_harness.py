"""Minimal isolated harness fixtures; no demonstration/evaluation data in Git."""

import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from scripts.pilot_package import VisibleSplit, copy_visible, safe_relative, verify_archive
from scripts.pilot_runtime import attest_visible_references, csv_subset
from scripts.pilot_score import exhaustive_subsets, matching_score, ratio


@pytest.mark.parametrize(
    "path",
    [
        "../x",
        "/x",
        "C:/x",
        "x\\y",
        "x//y",
        "./x",
        "x/../y",
        "x/",
        "x /y",
        "x./y",
        ".. /x",
        "NUL.txt",
        "COM1",
        "x|y",
        "x\x00y",
        "LPT9.txt",
    ],
)
def test_package_paths_reject_traversal_and_windows_aliases(path):
    with pytest.raises(ValueError, match="Unsafe package path"):
        safe_relative(path)


def tiny_archive(tmp_path, *, tamper=False, extra=False, symlink=False):
    name = "dev/imports/customers.csv"
    content = b"external_reference,name\nx,X\n"
    manifest = {
        "all_other_files": {
            name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        },
        "file_count_excluding_manifest": 1,
    }
    path = tmp_path / "minimal.zip"
    with ZipFile(path, "w") as zipped:
        zipped.writestr("clearledger_pilot_v1/MANIFEST.json", json.dumps(manifest))
        info = ZipInfo("clearledger_pilot_v1/" + name)
        if symlink:
            info.external_attr = 0o120777 << 16
        zipped.writestr(info, content + b"!" if tamper else content)
        if extra:
            zipped.writestr("clearledger_pilot_v1/unlisted.txt", b"x")
    return path


def test_every_manifest_member_is_verified_before_use(tmp_path):
    result = verify_archive(tiny_archive(tmp_path))
    assert result["files"] == 2 and result["verified_members"] == 1


@pytest.mark.parametrize("change", ["tamper", "extra", "symlink"])
def test_manifest_tamper_unlisted_data_and_symlinks_are_rejected(tmp_path, change):
    with pytest.raises(ValueError):
        verify_archive(tiny_archive(tmp_path, **{change: True}))


@pytest.mark.parametrize(
    "path",
    [
        "hidden_ground_truth/ground_truth_cases.jsonl",
        "SCENARIO_INDEX.json",
        "MANIFEST.json",
        "app_visible/evidence_corpus/x.canonical.txt",
        "app_visible/evidence_corpus/x.extraction.json",
        "app_visible/evidence_corpus/hidden_ground_truth/x.txt",
        "imports/other.csv",
        "app_visible/supplementary_erp_context/x.json",
    ],
)
def test_application_input_boundary_rejects_answers_and_parser_sidecars(tmp_path, path):
    view = VisibleSplit(tmp_path)
    with pytest.raises(ValueError, match="Forbidden application input"):
        view.read(path)
    assert view.reads == []


def test_copy_exposes_only_originals_and_four_financial_contracts(tmp_path):
    package = tmp_path / "package"
    split = package / "dev"
    for kind in ["customers", "payer-aliases", "invoices", "bank-transactions"]:
        p = split / f"imports/{kind}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"minimal-header\nminimal-row\n")
    corpus = split / "app_visible/evidence_corpus"
    corpus.mkdir(parents=True)
    (corpus / "x.txt").write_bytes(b"INVOICE: i")
    (corpus / "x.canonical.txt").write_text("ANSWER_CANARY")
    (corpus / "x.extraction.json").write_text('"ANSWER_CANARY"')
    (corpus / "evidence_inventory.jsonl").write_text(
        json.dumps({"source_path": "evidence_corpus/x.txt"})
    )
    (split / "app_visible/operational_events.jsonl").write_text("")
    hidden = split / "hidden_ground_truth"
    hidden.mkdir()
    (hidden / "answer.json").write_text('"ANSWER_CANARY"')
    destination = tmp_path / "application-input"
    view = copy_visible(package, "dev", destination)
    assert view.read("app_visible/evidence_corpus/x.txt") == b"INVOICE: i"
    files = [p for p in destination.rglob("*") if p.is_file()]
    assert len(files) == 7
    assert all(b"ANSWER_CANARY" not in p.read_bytes() for p in files)


def test_runner_and_scorer_have_one_way_dependency_boundary():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "scripts/pilot_runtime.py").read_text("utf-8"))
    imports = [
        ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    assert not any(
        "pilot_score" in statement or "pilot_package" in statement for statement in imports
    )
    score = ast.parse((root / "scripts/pilot_score.py").read_text("utf-8"))
    assert not any(
        isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("clearledger")
        for n in ast.walk(score)
    )


def test_simulated_attestation_requires_alias_owner_and_exact_delimited_reference():
    class API:
        def __init__(self):
            self.calls = []

        def request(self, method, path, **kwargs):
            self.calls.append(kwargs["json"])

            class Response:
                def json(self):
                    return kwargs["json"]

            return Response()

    api = API()
    receipt = {"id": "r", "bank_transaction_id": "b", "version": 1}
    bank = {
        "id": "b",
        "payer_name": "unknown",
        "memo": "i-1",
        "source_import_id": "s",
        "source_row": 2,
    }
    invoice = {"id": "i", "customer_id": "c", "invoice_number": "i-1", "version": 1}
    aliases = [{"normalized_alias": "alias", "customer_id": "c"}]
    assert attest_visible_references(api, [receipt], [bank], [invoice], aliases) == []
    bank["payer_name"] = "ALIAS"
    bank["memo"] = "i-10"
    assert attest_visible_references(api, [receipt], [bank], [invoice], aliases) == []
    bank["memo"] = "i-1"
    invoice["customer_id"] = "other"
    assert attest_visible_references(api, [receipt], [bank], [invoice], aliases) == []
    invoice["customer_id"] = "c"
    evidence = attest_visible_references(api, [receipt], [bank], [invoice], aliases)
    assert len(evidence) == 1 and len(api.calls) == 1
    assert evidence[0]["exact_quote"] == "i-1" and evidence[0]["kind"] == "INVOICE_REFERENCE"


def test_independent_oracle_distinguishes_duplicate_amount_identities():
    invoices = [
        {"invoice_number": "a", "open_amount_paise": 101},
        {"invoice_number": "b", "open_amount_paise": 101},
        {"invoice_number": "c", "open_amount_paise": 202},
    ]
    assert exhaustive_subsets(invoices, 202) == [{"c": 202}, {"a": 101, "b": 101}]
    assert ratio(0, 0)["rate"] is None


def test_negative_replay_request_is_derived_in_memory_and_preserves_input():
    raw = b"a,b\r\nx,1\r\n"
    assert csv_subset(raw, {"a": "x", "b": "2"}) == b"a,b\r\nx,2\r\n"
    assert raw == b"a,b\r\nx,1\r\n"


def score_fixture():
    natural = {"source_system": "s", "account_ref": "a", "external_transaction_id": "t"}
    records = {
        "customers": [{"id": "c", "external_reference": "x"}],
        "payer-aliases": [{"normalized_alias": "alias", "customer_id": "c"}],
        "invoices": [
            {
                "id": "i",
                "invoice_number": "n",
                "customer_id": "c",
                "status": "OPEN",
                "open_amount_paise": 101,
                "issued_date": "2025-01-01",
            }
        ],
        "bank-transactions": [
            {"id": "b", **natural, "payer_name": "alias", "occurred_at": "2025-01-02T00:00:00Z"}
        ],
        "receipts": [
            {
                "id": "r",
                "bank_transaction_id": "b",
                "amount_paise": 101,
                "unapplied_amount_paise": 101,
            }
        ],
    }
    exact = {
        "outcome": "NO_SUPPORTED_MATCH",
        "invoice_id": None,
        "amount_paise": 0,
        "customer_id": "c",
    }
    advanced = {
        "customer_id": "c",
        "result": {
            "outcome": "UNIQUE",
            "intent_verified": False,
            "reason": "MATHEMATICAL_UNIQUENESS_ONLY",
            "candidates": [{"allocations": [{"invoice_id": "i", "amount_paise": 101}]}],
            "partial_analysis": [],
        },
    }
    observed = {
        "records": records,
        "unattested": {"r": {"match": exact, "match-advanced": advanced}},
    }
    truth = {
        "primary_receipt_natural_key": natural,
        "linked_receipt_natural_keys": [],
        "true_customer_external_reference": "x",
        "expected_safe_matching_decision": "REVIEW",
        "claims_truth": [],
        "abstain_invoice_allocation": False,
        "scenario_id": "minimal",
        "stages": [{"incremental_cash_allocations_paise": {"t": {"n": 101}}}],
    }
    return observed, [truth]


def test_unattested_math_is_not_scored_as_supported_intent():
    observed, truth = score_fixture()
    score, _ = matching_score(observed, truth, "unattested")
    assert score["advanced_false_supported"] == {"false": 0, "supported": 0, "rate": None}
    assert score["exact_recall_full_balance_targets"]["correct"] == 0
    assert score["independent_subset_oracle"]["correct"] == 1


def test_scorer_detects_supported_wrong_customer_without_adjusting_runtime_inputs():
    observed, truth = score_fixture()
    result = observed["unattested"]["r"]
    result["match"].update(
        outcome="EXACT_MATCH", invoice_id="i", amount_paise=101, customer_id="wrong"
    )
    result["match-advanced"]["result"]["intent_verified"] = True
    result["match-advanced"]["customer_id"] = "wrong"
    score, _ = matching_score(observed, truth, "unattested")
    assert score["exact_false_supported"]["false"] == 1
    assert score["advanced_false_supported"]["false"] == 1
    assert score["exact_recall_full_balance_targets"]["correct"] == 0


def test_unmapped_receipts_fail_evaluation_instead_of_disappearing_from_denominators():
    observed, truth = score_fixture()
    truth[0]["primary_receipt_natural_key"]["external_transaction_id"] = "other"
    with pytest.raises(AssertionError, match="exactly one truth association"):
        matching_score(observed, truth, "unattested")
