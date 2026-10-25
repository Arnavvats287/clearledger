"""Minimal isolated harness fixtures, not benchmark construction or answer keys."""

import json
import sys
from pathlib import Path

import pytest
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, csv_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from application_eval_contract import latency_summary, snapshot_predictions  # noqa: E402
from application_eval_inputs import IMPORTS, Snapshot  # noqa: E402

CUTOFF = "2026-01-19T12:00:00+05:30"


def visible(tmp_path):
    root = tmp_path / "visible"
    (root / "imports").mkdir(parents=True)
    (root / "app_visible/correlation_sources").mkdir(parents=True)
    for kind, row in zip(IMPORTS, (CUSTOMER, ALIAS, INVOICE, BANK), strict=True):
        if kind == "bank-transactions":
            row = {**row, "payer_name": "Test Alias"}
        (root / f"imports/{kind}.csv").write_bytes(csv_bytes(kind, row))
    (root / "app_visible/correlation_sources/unit.json").write_text(
        json.dumps(
            {
                "remittance_version": "1.0",
                "invoice_references": ["i"],
                "utr_references": ["t"],
                "payer_hint": None,
                "claims": [],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_visible_input_seal_tamper_and_outside_reads(tmp_path):
    source = Snapshot(visible(tmp_path), CUTOFF)
    assert len(source.files) == 5 and not source.temporal_checks()
    with pytest.raises(ValueError, match="outside"):
        source.read("../hidden_ground_truth/answers.json")
    source.verify()
    (source.root / "imports/customers.csv").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        source.read("imports/customers.csv")
    with pytest.raises(ValueError, match="modified"):
        source.verify()


@pytest.mark.parametrize(
    "name",
    [
        "hidden_ground_truth/a.json",
        "templates/a.txt",
        "app_visible/evidence_corpus/sidecars/a.json",
        "generator.py",
        "RUNTIME_ALLOWLIST.json",
    ],
)
def test_non_application_inputs_are_not_accepted(tmp_path, name):
    root = visible(tmp_path)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not runtime data", encoding="utf-8")
    with pytest.raises(ValueError):
        Snapshot(root, CUTOFF)


def test_cutoff_is_explicit_and_future_cash_detected(tmp_path):
    root = visible(tmp_path)
    with pytest.raises(ValueError, match="timezone"):
        Snapshot(root, "2026-01-19T12:00:00")
    (root / "imports/bank-transactions.csv").write_bytes(
        csv_bytes("bank-transactions", {**BANK, "occurred_at": "2026-01-20T12:00:00+05:30"})
    )
    assert Snapshot(root, CUTOFF).temporal_checks() == [
        {"kind": "bank-transactions", "row": 2, "code": "AFTER_EXPORT_CUTOFF"}
    ]


def test_predictions_do_not_turn_uniqueness_into_verified_allocations():
    bank = {"id": "b", "source_system": "s", "account_ref": "a", "external_transaction_id": "t"}
    data = {
        "bank-transactions": [bank],
        "customers": [{"id": "c", "external_reference": "x"}],
        "receipts": [{"id": "r", "bank_transaction_id": "b"}],
    }
    matching = {
        "r": {
            "match-advanced": {
                "customer_id": "c",
                "outcome": "UNIQUE",
                "result": {"intent_verified": False},
            }
        }
    }
    predicted = snapshot_predictions(data, matching, CUTOFF)[0]
    assert predicted["receipt"] == {
        k: bank[k] for k in ("source_system", "account_ref", "external_transaction_id")
    }
    assert predicted["abstain_invoice_allocation"] and predicted["cash_allocations"] == []
    assert "journal_proposal" not in predicted and "claim_assessments" not in predicted
    matching["r"]["match-advanced"]["result"]["intent_verified"] = True
    with pytest.raises(ValueError, match="verified intent"):
        snapshot_predictions(data, matching, CUTOFF)


def test_latency_denominators_and_no_empty_perfect_result():
    assert latency_summary([])["p95_ns"] is None
    assert latency_summary([1, 2, 3, 4, 5]) == {"count": 5, "p50_ns": 3, "p95_ns": 5, "max_ns": 5}


def test_role_login_does_not_depend_on_machine_uptime(monkeypatch):
    import application_eval_host

    class Reply:
        status_code = 200

        def json(self):
            return {"access_token": "isolated-clock-test-token"}

    class Client:
        logged_in = False

        def post(self, path, **kwargs):
            assert path == "/review/demo/login"
            self.logged_in = True
            return Reply()

        def request(self, method, path, **kwargs):
            assert self.logged_in
            assert kwargs["headers"]["Authorization"] == "ReviewDemo isolated-clock-test-token"
            return Reply()

    monkeypatch.setattr(application_eval_host.time, "monotonic", lambda: 10)
    api = application_eval_host.API(Client(), "isolated-password")
    assert api.request("GET", "/customers").status_code == 200


@pytest.mark.postgres
def test_real_api_snapshot_role_boundary_and_nonmutation(disposable_database, tmp_path):
    from application_eval_runtime import run

    source = Snapshot(visible(tmp_path), CUTOFF)
    output = tmp_path / "output"
    output.mkdir()
    observations, summary = run(
        source, disposable_database.render_as_string(hide_password=False), output
    )
    source.verify()
    assert summary["record_counts"]["receipts"] == 1
    assert summary["financial_mutations"] == 0 and summary["financial_identity_status"] == 503
    assert summary["external_provider_reservations"] == 0
    assert summary["positive_spans"] == 1 and summary["forged_spans_rejected"] == 1
    assert summary["extraction_states"] == {"SUCCEEDED": 1}
    assert all(i["status"] == 200 for i in observations["imports"])
    assert observations["snapshot_predictions"][0]["abstain_invoice_allocation"]
    assert summary["receipt_unapplied_paise"] == 100
    assert summary["unresolved_invoice_open_paise"] == 100
    assert len(observations["investigation"]["evidence_queries"]) == 1
    assert observations["investigation"]["evidence_queries"][0]["status"] == 200
