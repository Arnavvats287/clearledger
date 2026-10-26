"""Executable portfolio walkthrough using existing minimal, isolated code fixtures."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from test_advanced_matching import advanced, prepare
from test_cases import correlate, pump
from test_documents import auth, extract, get, upload
from test_evidence import SOURCE_SECRET, fixture_case, manifest, register
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_investigations import run, start
from test_matching import add_evidence, financial_state, match, setup

pytestmark = pytest.mark.postgres
OUTPUT = Path(__file__).resolve().parents[1] / "local-data/portfolio-demo"


def save(name, observation):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{name}.json").write_text(json.dumps(observation, indent=2), encoding="utf-8")


def test_complete_accountant_review_workflow(documents_environment):
    """One invoice/receipt/case chain; 1101 = 1000 cash candidate + 101 disputed rebate."""
    env = documents_environment
    client = env[3]
    assert not client.app.state.settings.external_ai_enabled
    assert client.app.state.settings.investigation_provider == "deterministic"
    assert client.app.state.finance_identity_verifier is None
    # Small variants of existing isolated API fixtures, not a generated dataset.
    receipt_id = prepare(client, amounts=(1101,), cash=1000)
    before = financial_state(client)
    invoice = before["/invoices"][0]
    receipt = before["/receipts"][0]
    assert invoice["open_amount_paise"] == 1101 and receipt["unapplied_amount_paise"] == 1000
    no_intent = advanced(client, receipt_id)
    assert no_intent.status_code == 200
    assert no_intent.json()["outcome"] == "UNRESOLVED"
    assert not no_intent.json()["result"]["candidates"]
    attestation = add_evidence(client, receipt_id)
    assert attestation.status_code == 200
    proposal_response = advanced(client, receipt_id)
    assert proposal_response.status_code == 200
    proposal = proposal_response.json()
    assert proposal["outcome"] == "UNIQUE" and proposal["result"]["intent_verified"]
    candidate = proposal["result"]["candidates"][0]
    assert candidate["total_paise"] == 1000 and candidate["remaining_cash_paise"] == 0
    allocation = candidate["allocations"][0]
    assert allocation["invoice_id"] == invoice["id"]
    assert allocation["remaining_ar_paise"] == 101 and allocation["reference_evidence_ids"]

    raw = b"INVOICE: i\nUTR: t\nCLAIM rebate: INR 1.01"
    uploaded = upload(client, raw)
    assert uploaded.status_code == 200
    document = uploaded.json()
    extraction = extract(client, document["id"]).json()
    assert extraction["route"] == "DETERMINISTIC" and extraction["status"] == "SUCCEEDED"
    assert extraction["result"]["claims"][0]["amount_paise"] == 101
    assert extraction["result"]["claims"][0]["category"] == "rebate"
    assert document["content_sha256"] == hashlib.sha256(raw).hexdigest()
    association = correlate(client, document, extraction, receipt)
    assert association.status_code == 200 and association.json()["status"] == "LINKED"
    pump(env)
    cases = get(client, "/cases").json()
    assert len(cases) == 1
    case = cases[0]
    assert receipt_id in case["receipt_ids"] and invoice["id"] in case["invoice_ids"]
    assert document["id"] in case["document_ids"]
    claims = get(client, f"/cases/{case['id']}/claims").json()
    assert len(claims) == 1 and claims[0]["amount_paise"] == 101
    claim = claims[0]
    assert claim["document_id"] == document["id"] and claim["source_current"]

    # Explicit test publisher trust, never production authentication or hidden answers.
    client.app.state.settings.evidence_trusted_sources_json = SecretStr(
        json.dumps(
            [
                {
                    "organization_id": str(env[1]),
                    "source_system": "test-origin",
                    "key_id": "test-key",
                    "secret": SOURCE_SECRET,
                    "allowed_kinds": ["PROMOTION"],
                }
            ]
        )
    )
    source = register(env, manifest(env, kind="PROMOTION", category="rebate", value=101))
    assert source.status_code == 200 and source.json()["source_authenticated"]
    source = source.json()
    pump(env)
    queued = start(env, case, claim)
    assert queued.status_code == 200
    identifier = queued.json()["id"]
    assert run(env, identifier) == "DELIVERED"
    findings = get(client, f"/investigations/{identifier}/findings").json()
    assert len(findings) == 1
    finding = findings[0]
    assert finding["claim_id"] == claim["id"] and finding["state"] == "SUPPORTED"
    assert finding["next_action"] == "HUMAN_REVIEW" and finding["requires_human_review"]
    assert finding["is_current"] and not finding["financial_authority"]
    assert [p["record_id"] for p in finding["citations"]] == [source["id"]]
    assert finding["citations"][0]["raw_sha256"] == source["citation"]["raw_sha256"]
    assert any(
        "SOURCE_FACTS_SUPPORT_PREDICATE_ONLY" in f["reasons"] for f in finding["source_facts"]
    )
    review = get(client, f"/cases/{case['id']}").json()
    assert review["state"] == "AWAITING_REVIEW" and review["claimed_total_paise"] == 101
    assert review["verified_settled_paise"] == 0 and not review["financial_authority"]
    assert get(client, f"/cases/{case['id']}/events").json()
    assert get(client, f"/investigations/{identifier}/trace").json()
    assert financial_state(client) == before
    save(
        "accountant",
        {
            "workflow_complete_to_review": True,
            "invoice_open_paise": 1101,
            "receipt_unapplied_paise": 1000,
            "unattested_outcome": no_intent.json()["outcome"],
            "candidate_outcome": "UNIQUE",
            "candidate_cash_paise": 1000,
            "candidate_remaining_ar_paise": 101,
            "claimed_rebate_paise": 101,
            "remittance_receipt_link": association.json()["status"],
            "finding": finding["state"],
            "next_action": finding["next_action"],
            "case_state": review["state"],
            "verified_settled_paise": 0,
            "citation_records": len(finding["citations"]),
            "financial_nonmutation": True,
            "requires_human_review": True,
            "financial_authority": False,
            "test_only_intent_and_publisher_attestations": True,
        },
    )


def test_ingestion_matching_document_and_audit_walkthrough(documents_environment):
    _, _, _, client, _ = documents_environment
    assert not client.app.state.settings.external_ai_enabled
    assert client.app.state.settings.investigation_provider == "deterministic"
    assert client.app.state.finance_identity_verifier is None
    receipt = setup(client)
    before = financial_state(client)
    unsupported = match(client, receipt)
    assert unsupported.status_code == 200
    assert unsupported.json()["outcome"] == "NO_SUPPORTED_MATCH"
    # Explicit synthetic test attestation, never inferred verified intent from text.
    assert add_evidence(client, receipt).status_code == 200
    key = uuid4()
    exact = match(client, receipt, key=key)
    assert exact.status_code == 200
    assert exact.json()["outcome"] == "EXACT_MATCH" and exact.json()["amount_paise"] == 100
    assert match(client, receipt, key=key).json() == exact.json()
    raw = b"INVOICE: i\nUTR: t\nCLAIM rebate: INR 1.01"
    document = upload(client, raw).json()
    extraction = extract(client, document["id"]).json()
    assert extraction["route"] == "DETERMINISTIC" and extraction["status"] == "SUCCEEDED"
    assert extraction["result"]["invoice_references"][0]["value"] == "i"
    assert extraction["result"]["claims"][0]["amount_paise"] == 101
    assert extraction["requires_human_review"] and not extraction["financial_authority"]
    assert get(client, f"/documents/{document['id']}/original").content == raw
    assert document["content_sha256"] == hashlib.sha256(raw).hexdigest()
    pointers = [
        entry["span"]
        for field in ("invoice_references", "utr_references")
        for entry in extraction["result"][field]
    ]
    pointers += [
        extraction["result"]["claims"][0][field] for field in ("description", "amount_span")
    ]
    for pointer in pointers:
        verified = client.post(
            f"/documents/{document['id']}/verify-span", headers=auth(), json=pointer
        )
        assert verified.status_code == 200 and verified.json()["source_consistent"]
    events = get(client, f"/documents/{document['id']}/events").json()
    assert {"document.ingested", "document.extracted"} <= {e["event_type"] for e in events}
    imports = client.get("/imports").json()
    audit = client.get("/audit/events").json()
    assert len(imports) == 4 and audit
    import_ids = {row["id"] for row in imports}
    for path in ("/invoices", "/bank-transactions", "/payer-aliases"):
        for row in before[path]:
            assert row["source_import_id"] in import_ids and row["source_row"] >= 1
    assert all(row["source_import_id"] in import_ids for row in audit)
    assert document["content_sha256"] and document["canonical_sha256"]
    assert financial_state(client) == before
    save(
        "ingestion",
        {
            "customers": len(before["/customers"]),
            "invoices": len(before["/invoices"]),
            "bank_transactions": len(before["/bank-transactions"]),
            "receipts": len(before["/receipts"]),
            "matching_without_intent": unsupported.json()["outcome"],
            "matching_with_test_attestation": exact.json()["outcome"],
            "proposal_amount_paise": 100,
            "extraction_route": extraction["route"],
            "extraction_status": extraction["status"],
            "claim_amount_paise": 101,
            "human_review_required": True,
            "financial_authority": False,
            "source_imports": len(imports),
            "source_rows_linked": True,
            "source_span_checks": len(pointers),
            "audit_events": len(audit),
            "document_event_types": sorted(e["event_type"] for e in events),
            "original_sha256": document["content_sha256"],
            "canonical_sha256": document["canonical_sha256"],
            "financial_nonmutation": True,
            "idempotent_matching_replay": True,
        },
    )


@pytest.mark.parametrize("mode", ["supported", "missing", "conflict"])
def test_real_langgraph_evidence_walkthrough(documents_environment, mode):
    env = documents_environment
    client = env[3]
    assert not client.app.state.settings.external_ai_enabled
    assert client.app.state.settings.investigation_provider == "deterministic"
    assert client.app.state.finance_identity_verifier is None
    case, claim = fixture_case(env, category="rebate")
    if mode != "missing":
        assert register(env, manifest(env, kind="PROMOTION", category="rebate")).status_code == 200
        if mode == "conflict":
            assert (
                register(
                    env, manifest(env, kind="PROMOTION", category="rebate", value=100)
                ).status_code
                == 200
            )
        pump(env)
    before = financial_state(client)
    response = start(env, case, claim)
    assert response.status_code == 200
    identifier = response.json()["id"]
    assert run(env, identifier) == "DELIVERED"
    summary = get(client, f"/investigations/{identifier}").json()
    finding = get(client, f"/investigations/{identifier}/findings").json()[0]
    trace = get(client, f"/investigations/{identifier}/trace").json()
    events = get(client, f"/cases/{case['id']}/events").json()
    assert finding["state"] == ("SUPPORTED" if mode == "supported" else "INSUFFICIENT_EVIDENCE")
    assert finding["requires_human_review"] and not finding["financial_authority"]
    assert finding["is_current"] and not summary["is_stale"]
    assert summary["recommendation"] == "AWAITING_REVIEW"
    assert summary["tool_calls"] > 0 and trace and events
    if mode == "supported":
        assert finding["citations"] and finding["source_facts"]
    if mode == "conflict":
        assert any("CONFLICTING_EVIDENCE" in fact["reasons"] for fact in finding["source_facts"])
    if mode == "missing":
        assert any("MISSING_EVIDENCE" in fact["reasons"] for fact in finding["source_facts"])
    assert financial_state(client) == before
    save(
        mode,
        {
            "state": finding["state"],
            "next_action": finding["next_action"],
            "recommendation": summary["recommendation"],
            "citations": len(finding["citations"]),
            "tool_calls": summary["tool_calls"],
            "provider": summary["provider"],
            "source_reasons": [fact["reasons"] for fact in finding["source_facts"]],
            "trace_nodes": [entry["node"] for entry in trace],
            "case_events": len(events),
            "financial_nonmutation": True,
            "requires_human_review": True,
            "financial_authority": False,
            "test_only_source_trust": True,
        },
    )
