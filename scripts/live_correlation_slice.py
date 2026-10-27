"""One application-owned synthetic slice; no live provider or output repair here."""

import json
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ai_usefulness import PROSE
from test_cases import pump
from test_documents import get
from test_evidence import SOURCE_SECRET, register, sign
from test_finance import FixtureIdentities, headers
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, post

from clearledger.finance_models import (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)

# Original approved free-form clause, plus existing synthetic source-contract labels.
# These independently signed fixture fields are never inferred from model output.
RAW = PROSE + "\nCUSTOMER: c\nINVOICE: I-1\nUTR: t\nAMOUNT: 101 paise"


def prepare(api, engine, org, settings, *, investigation_sources=False):
    for kind, row in (
        ("customers", CUSTOMER),
        (
            "invoices",
            {
                **INVOICE,
                "invoice_number": "I-1",
                "original_amount_paise": "1001",
                "open_amount_paise": "1001",
            },
        ),
        ("payer-aliases", ALIAS),
        ("bank-transactions", {**BANK, "amount_paise": "900", "payer_name": "Test Alias"}),
    ):
        assert post(api, kind, row).status_code == 200
    settings.case_auto_correlate_extractions = True
    settings.case_auto_investigate_extractions = True
    settings.evidence_trusted_sources_json = SecretStr(
        json.dumps(
            [
                {
                    "organization_id": str(org),
                    "source_system": "test-origin",
                    "key_id": "test-key",
                    "secret": SOURCE_SECRET,
                    "allowed_kinds": ["REMITTANCE", "WMS", "POD"]
                    if investigation_sources
                    else ["REMITTANCE"],
                }
            ]
        )
    )
    identities = FixtureIdentities(org)
    for name, principal in identities.users.items():
        permissions = {"REVIEW_READ"}
        if name in {"controller", "checker"}:
            permissions |= {"REVIEW_WORK", "REVIEW_CONTROL"}
        identities.users[name] = principal.model_copy(
            update={"permissions": frozenset(permissions)}
        )
    api.app.state.finance_identity_verifier = identities
    return (engine, org, None, api, api)


def finish(env, doc, extraction):
    """Only called after unmodified provider output passes every acceptance assertion."""
    engine, org, _, api, _ = env
    pump(env)
    case = next(c for c in get(api, "/cases").json() if doc["id"] in c["document_ids"])
    claims = get(api, f"/cases/{case['id']}/claims").json()
    assert len(claims) == 1 and claims[0]["amount_paise"] == 101
    claim = claims[0]
    assert claim["document_id"] == doc["id"] and claim["source_current"]
    initial_runs = get(api, f"/cases/{case['id']}/investigations").json()
    assert len(initial_runs) == 1

    def tasks():
        response = api.get(
            f"/review/cases/{case['id']}/correlation-tasks", headers=headers("controller")
        )
        assert response.status_code == 200
        return response.json()

    missing = tasks()[0]
    assert missing["reason"] == "MISSING_AUTHENTICATED_CORRELATION_EVIDENCE"
    assert not missing["candidates"] and not case["receipt_ids"]
    customer = api.get("/customers").json()[0]
    invoice = api.get("/invoices").json()[0]
    receipt = api.get("/receipts").json()[0]

    def span(quote, *, last=False):
        start = RAW.rindex(quote) if last else RAW.index(quote)
        return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

    manifest = {
        "source_system": "test-origin",
        "source_record_id": "unit-live-remittance",
        "revision": 1,
        "customer_id": customer["id"],
        "invoice_id": invoice["id"],
        "document_id": doc["id"],
        "document_version": doc["version"],
        "raw_sha256": doc["content_sha256"],
        "canonical_sha256": doc["canonical_sha256"],
        "excerpt": span(RAW),
        "customer_reference": {
            "value": "c",
            "span": span("c\n") | {"end": RAW.index("c\n") + 1, "quote": "c"},
        },
        "invoice_reference": {"value": "I-1", "span": span("I-1", last=True)},
        "categories": ["damage"],
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "occurred_at": "2026-01-01T00:00:00Z",
        "recorded_at": "2026-01-02T00:00:00Z",
        "signed_at": "2026-01-01T00:00:00Z",
        "approved_at": "2026-01-01T00:00:00Z",
        "date_basis": "INVOICE_ISSUED",
        "fact": {"type": "REMITTANCE", "amount": {"value": 101, "span": span("101 paise")}},
    }
    registered = register(env, sign(env, manifest))
    assert registered.status_code == 200 and registered.json()["source_authenticated"]
    pump(env)
    task = tasks()[0]
    assert task["id"] != missing["id"] and task["reason"] == "READY_FOR_REVIEW"
    assert len(task["candidates"]) == 1
    candidate = task["candidates"][0]
    assert candidate["invoice_id"] == invoice["id"] and candidate["receipt_id"] == receipt["id"]
    current = get(api, f"/cases/{case['id']}").json()
    payload = {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "expected_task_sha256": task["input_sha256"],
        "decision": "CONFIRM",
    }
    decision_key = uuid4()
    decision = api.post(
        f"/review/correlation-tasks/{task['id']}/decision",
        json=payload,
        headers=headers("controller", decision_key),
    )
    assert decision.status_code == 200
    assert not decision.json()["financial_authority"]
    pump(env)
    merged = get(api, f"/cases/{case['id']}").json()
    assert merged["receipt_ids"] == [receipt["id"]] and merged["invoice_ids"] == [invoice["id"]]
    assert merged["document_ids"] == [doc["id"]] and merged["customer_id"] == customer["id"]
    assert not merged["is_stale"]
    final_claims = get(api, f"/cases/{merged['id']}/claims").json()
    assert [c["id"] for c in final_claims] == [claim["id"]]
    associations = get(api, f"/documents/{doc['id']}/associations").json()
    assert len(associations) == 1 and not associations[0]["is_stale"]
    assert associations[0]["extraction_id"] == extraction["id"]
    history = api.get(
        f"/review/correlation-tasks/{task['id']}/decisions", headers=headers("controller")
    ).json()
    assert len(history) == 1 and history[0]["id"] == decision.json()["id"]
    runs = get(api, f"/cases/{merged['id']}/investigations").json()
    current_run = next(r for r in runs if not r["is_stale"])
    assert current_run["id"] != initial_runs[0]["id"]
    findings = get(api, f"/investigations/{current_run['id']}/findings").json()
    trace = get(api, f"/investigations/{current_run['id']}/trace").json()
    assert trace and findings[0]["citations"] and findings[0]["source_facts"]
    assert findings[0]["claim_id"] == claim["id"] and findings[0]["is_current"]
    assert findings[0]["requires_human_review"] and not findings[0]["financial_authority"]
    assert current_run["recommendation"] == "AWAITING_REVIEW"
    assert pump(env) == {}
    assert len(get(api, f"/cases/{merged['id']}/investigations").json()) == len(runs)
    with Session(engine) as session:
        for model in (
            CashAllocation,
            NoncashSettlement,
            LedgerJournal,
            LedgerLine,
            AccountBalance,
            FinanceApproval,
        ):
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.organization_id == org)
                )
                == 0
            )
    assert UUID(claim["document_id"]) == UUID(doc["id"])
    return {
        "before_case": case,
        "claim": claim,
        "missing_task": missing,
        "ready_task": task,
        "decision_payload": payload,
        "decision": decision.json(),
        "decision_key": str(decision_key),
        "evidence_record": registered.json(),
        "decision_history": history,
        "canonical_case": merged,
        "association": associations[0],
        "investigation": current_run,
        "findings": findings,
        "trace": trace,
        "next_action": current_run["recommendation"],
        "same_financial_and_claim_ids": True,
        "no_allocations_settlements_journals": True,
        "synthetic_identity_only": True,
    }
