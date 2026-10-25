"""Isolated accounting mechanics fixtures, never Argon/evaluation data or real identities."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_advanced_matching import advanced, attest, prepare
from test_cases import correlate, pump
from test_documents import auth, extract, get, upload
from test_documents import documents_environment as documents_environment
from test_documents import environment as environment
from test_evidence import SOURCE_SECRET, manifest, register

from clearledger.finance_identity import Principal
from clearledger.finance_models import (
    CashAllocation,
    FinanceProposal,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)

pytestmark = pytest.mark.postgres


class FixtureIdentities:
    """Test-only authenticated identity fixture. Never installed by create_app."""

    def __init__(self, org):
        now = datetime.now(UTC)
        permissions = {
            "analyst": {"FINANCE_READ", "PROPOSE"},
            "controller": {
                "FINANCE_READ",
                "PROPOSE",
                "REVIEW_SOURCES",
                "REVIEW_POLICY",
                "REVIEW_TAX_POLICY",
                "APPROVE",
            },
            "checker": {"FINANCE_READ", "PROPOSE", "APPROVE"},
            "poster": {"FINANCE_READ", "SIMULATE_POST"},
            "auditor": {"FINANCE_READ"},
        }
        self.users = {
            name: Principal(
                issuer="isolated-test-issuer",
                subject=uuid5(NAMESPACE_URL, f"isolated-finance-identity:{org}:{name}"),
                organization_id=org,
                authorization_version="1",
                permissions=frozenset(values),
                service=name == "poster",
                authenticated_at=now - timedelta(seconds=1),
                expires_at=now + timedelta(hours=1),
            )
            for name, values in permissions.items()
        }
        self.revoked = set()

    def authenticate(self, request):
        return self.users[request.headers["authorization"].removeprefix("FixtureFinance ")]

    def revalidate(self, provenance):
        if provenance["subject"] in self.revoked:
            raise ValueError("revoked")
        return next(p for p in self.users.values() if str(p.subject) == provenance["subject"])


def headers(actor="analyst", key=None):
    return {"Authorization": "FixtureFinance " + actor, "Idempotency-Key": str(key or uuid4())}


def command(row):
    return {"expected_version": row["version"], "expected_snapshot_sha256": row["snapshot_sha256"]}


def prepared(
    env,
    *,
    tax=True,
    amount=11650000,
    invoice=12000000,
    approved_fixture=True,
    apply_amount=None,
    category="damage",
    policy_changes=None,
    tax_kind="INCOME_TAX",
    tax_source_trusted=True,
    extra_tax_value=None,
    tax_rule_date="2026-01-01",
):
    client = env[3]
    identities = FixtureIdentities(env[1])
    client.app.state.finance_identity_verifier = identities
    receipt_id = prepare(client, amounts=(invoice,), cash=amount, memo="i")
    attest(client, receipt_id, "i")
    matched = advanced(client, receipt_id)
    assert matched.status_code == 200 and matched.json()["outcome"] == "UNIQUE", matched.text
    raw = (
        b"INVOICE: i\nUTR: t\nCLAIM tax: INR 1000.00\nCLAIM damage: INR 2500.00"
        if tax
        else f"INVOICE: i\nUTR: t\nCLAIM {category}: INR 1.01".encode()
    )
    doc = upload(client, raw).json()
    extraction = extract(client, doc["id"]).json()
    assert correlate(client, doc, extraction, client.get("/receipts").json()[0]).status_code == 200
    pump(env)
    case = get(client, "/cases").json()[0]
    claims = get(client, f"/cases/{case['id']}/claims").json()
    settings = client.app.state.settings
    settings.evidence_trusted_sources_json = SecretStr(
        json.dumps(
            [
                {
                    "organization_id": str(env[1]),
                    "source_system": "test-origin",
                    "key_id": "test-key",
                    "secret": SOURCE_SECRET,
                    "allowed_kinds": ["TAX", "PROMOTION", "WMS", "POD", "CONTRACT"],
                }
            ]
        )
    )
    source = None
    if tax:
        from test_evidence import sign

        body = manifest(env, kind="TAX", category="tax", value=100000, trusted=tax_source_trusted)
        body["fact"]["tax_tag"] = {
            "INCOME_TAX": "INCOME_TAX_TDS",
            "GST_TAX": "GST_TDS",
            "UNKNOWN": "UNKNOWN",
        }[tax_kind]
        if tax_source_trusted:
            body = sign(env, body)
        source = register(env, body)
        assert source.status_code == 200, source.text
        if extra_tax_value is not None:
            assert (
                register(
                    env, manifest(env, kind="TAX", category="tax", value=extra_tax_value)
                ).status_code
                == 200
            )
        pump(env)
        case = get(client, f"/cases/{case['id']}").json()
    invoice_id = client.get("/invoices").json()[0]["id"]
    base = {
        "expected_case_version": case["version"],
        "expected_context_sha256": case["context_sha256"],
        "matching_proposal_id": matched.json()["id"],
        "cash": [{"invoice_id": invoice_id, "amount_paise": apply_amount or amount}],
    }
    reviewed = client.post(
        f"/cases/{case['id']}/finance-source-reviews", json=base, headers=headers("controller")
    )
    assert reviewed.status_code == 200, reviewed.text
    rules = []
    if tax:
        claim = next(c for c in claims if c["category"] == "tax")
        rules = [
            {
                "id": "CASE-204-TAX",
                "category": "tax",
                "treatment": tax_kind if tax_kind != "UNKNOWN" else "INCOME_TAX",
                "approved_fixture": approved_fixture,
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "date_of_deduction": tax_rule_date,
                "case_id": case["id"],
                "customer_id": case["customer_id"],
                "receipt_id": receipt_id,
                "invoice_id": invoice_id,
                "claim_id": claim["id"],
                "amount_paise": 100000,
                "required_evidence": [source.json()["id"]],
                "recognition_policy": "REVIEWED_NONCASH_RECEIVABLE",
            }
        ]
    policy_body = {
        "reference": "isolated-test-policy",
        "version": 1,
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "rules": rules,
    }
    policy_body.update(policy_changes or {})
    policy = client.post("/finance/policies", json=policy_body, headers=headers("controller"))
    assert policy.status_code == 200, policy.text
    payload = {
        **base,
        "policy_id": policy.json()["id"],
        "source_review_id": reviewed.json()["id"],
        "claims": [
            {
                "claim_id": c["id"],
                "invoice_id": invoice_id,
                "rule_id": "CASE-204-TAX" if c["category"] == "tax" else None,
            }
            for c in claims
        ],
    }
    return case, claims, payload, identities


def proposed(env, **kwargs):
    case, claims, payload, identities = prepared(env, **kwargs)
    response = env[3].post(
        f"/cases/{case['id']}/journal-proposals", json=payload, headers=headers()
    )
    assert response.status_code == 200, response.text
    return case, claims, response.json(), payload, identities


def approved(env, **kwargs):
    case, claims, row, payload, identities = proposed(env, **kwargs)
    response = env[3].post(
        f"/journal-proposals/{row['id']}/request-approval", json=command(row), headers=headers()
    )
    assert response.status_code == 200, response.text
    response = env[3].post(
        f"/journal-proposals/{row['id']}/review",
        headers=headers("controller"),
        json={**command(response.json()), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert response.status_code == 200, response.text
    return case, claims, response.json(), payload, identities


def test_case_204_two_journals_open_damage_ar(documents_environment):
    env = documents_environment
    case, claims, row, _, _ = approved(env)
    response = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["journal_ids"]) == 2
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 250000
    assert env[3].get("/receipts").json()[0]["unapplied_amount_paise"] == 0
    current = get(env[3], f"/cases/{case['id']}").json()
    assert current["state"] == "PARTIALLY_SETTLED" and current["customer_id"] == case["customer_id"]
    assert current["verified_settled_paise"] == 100000
    states = {c["category"]: c["state"] for c in get(env[3], f"/cases/{case['id']}/claims").json()}
    assert states == {"tax": "RESOLVED", "damage": "AWAITING_CUSTOMER_EVIDENCE"}
    ledger = env[3].get("/finance/journals", headers=headers("auditor")).json()
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/demo-case.json").read_text())
    for journal in ledger:
        assert sum(line["debit_paise"] for line in journal["lines"]) == sum(
            line["credit_paise"] for line in journal["lines"]
        )
        expected = fixture["expected"][
            "receipt_journal" if journal["kind"] == "BANK" else "application_journal"
        ]
        assert [
            (line["account_code"], line["debit_paise"])
            for line in journal["lines"]
            if line["debit_paise"]
        ] == [(line["account"], line["amount_paise"]) for line in expected["debits"]]
        assert [
            (line["account_code"], line["credit_paise"])
            for line in journal["lines"]
            if line["credit_paise"]
        ] == [(line["account"], line["amount_paise"]) for line in expected["credits"]]
    with Session(env[0]) as session:
        assert len(list(session.scalars(select(CashAllocation)))) == 1
        assert len(list(session.scalars(select(NoncashSettlement)))) == 1


def test_no_verified_identity_means_no_finance_authority(documents_environment):
    client = documents_environment[3]
    response = client.post(
        "/finance/policies",
        headers={**auth(), "X-Actor-ID": "CONTROLLER"},
        json={
            "reference": "fake",
            "version": 1,
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
        },
    )
    assert response.status_code == 503


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_post_and_replays_are_one_ledger_result(documents_environment, same_key):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    env = documents_environment
    _, _, row, _, _ = approved(env)
    barrier, key = Barrier(2), uuid4()

    def attempt(_):
        barrier.wait(timeout=10)
        return env[3].post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster", key if same_key else uuid4()),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    again = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert again.status_code == 200 and again.json() == responses[0].json()
    with Session(env[0]) as session:
        assert len(list(session.scalars(select(LedgerJournal)))) == 2
        assert len(list(session.scalars(select(CashAllocation)))) == 1
        assert len(list(session.scalars(select(NoncashSettlement)))) == 1
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 250000


@pytest.mark.parametrize(
    "fault", ["invoice", "receipt", "policy", "evidence", "original", "approval_expired", "revoked"]
)
def test_stale_or_revoked_posting_is_rejected(documents_environment, fault):
    from test_evidence import sign

    env = documents_environment
    _, _, row, payload, identities = approved(
        env, policy_changes={"approval_ttl_seconds": 1} if fault == "approval_expired" else None
    )
    if fault in {"invoice", "receipt"}:
        table = "invoices" if fault == "invoice" else "receipts"
        column = "open_amount_paise" if fault == "invoice" else "unapplied_amount_paise"
        changes = ",status='PARTIALLY_APPLIED'" if fault == "receipt" else ""
        with env[0].begin() as connection:
            connection.execute(
                text(f"UPDATE {table} SET {column}={column}-1,version=version+1{changes}")
            )
    elif fault == "policy":
        spec = env[3].get("/finance/policies", headers=headers("auditor")).json()[0]["spec"]
        spec.update(version=2, previous_id=payload["policy_id"])
        assert (
            env[3].post("/finance/policies", json=spec, headers=headers("controller")).status_code
            == 200
        )
    elif fault == "evidence":
        with Session(env[0]) as session:
            from clearledger.evidence_models import EvidenceRecord

            source = session.scalar(select(EvidenceRecord))
            body = {**source.manifest, "revision": 2, "previous_id": str(source.id)}
        assert register(env, sign(env, body)).status_code == 200
    elif fault == "original":
        with Session(env[0]) as session:
            from clearledger.document_runtime import LocalOriginals
            from clearledger.evidence_models import EvidenceRecord
            from clearledger.models import Document

            record = session.scalar(select(EvidenceRecord))
            doc = session.get(Document, record.document_id)
            store = LocalOriginals(env[3].app.state.settings.document_root)
            store.path(env[1], doc.content_sha256).write_bytes(b"tampered")
    elif fault == "approval_expired":
        import time

        time.sleep(1.1)
    else:
        identities.revoked.add(str(identities.users["controller"].subject))
    response = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert response.status_code in {403, 409}, response.text
    with Session(env[0]) as session:
        assert not list(session.scalars(select(LedgerJournal)))
        assert not list(session.scalars(select(CashAllocation)))
        assert not list(session.scalars(select(NoncashSettlement)))


@pytest.mark.parametrize(
    "actor,operation",
    [
        ("auditor", "propose"),
        ("analyst", "approve"),
        ("controller", "post"),
        ("auditor", "post"),
        ("poster", "approve"),
        ("poster", "propose"),
    ],
)
def test_permission_and_service_boundaries(documents_environment, actor, operation):
    env = documents_environment
    case, _, row, payload, _ = proposed(env)
    path, body = (
        (f"/cases/{case['id']}/journal-proposals", payload)
        if operation == "propose"
        else (
            f"/journal-proposals/{row['id']}/review",
            {**command(row), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
        )
        if operation == "approve"
        else (f"/journal-proposals/{row['id']}/simulate-post", command(row))
    )
    response = env[3].post(path, json=body, headers=headers(actor))
    assert response.status_code == 403, response.text
    with Session(env[0]) as session:
        assert not list(session.scalars(select(LedgerJournal)))


def test_self_approval_and_spoofed_actor_denied(documents_environment):
    env = documents_environment
    case, _, payload, identities = prepared(env)
    row = (
        env[3]
        .post(f"/cases/{case['id']}/journal-proposals", json=payload, headers=headers("controller"))
        .json()
    )
    submitted = env[3].post(
        f"/journal-proposals/{row['id']}/request-approval",
        json=command(row),
        headers=headers("controller"),
    )
    assert submitted.status_code == 200, submitted.text
    response = env[3].post(
        f"/journal-proposals/{row['id']}/review",
        headers={**headers("controller"), "X-Actor-ID": "different-controller"},
        json={**command(submitted.json()), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert response.status_code == 403 and "MAKER_CHECKER" in response.text
    response = env[3].post(
        f"/journal-proposals/{row['id']}/review",
        headers=auth(),
        json={**command(submitted.json()), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert response.status_code == 401


def test_unreviewed_tax_abstains_without_writeoff(documents_environment):
    env = documents_environment
    _, _, row, _, _ = approved(env, approved_fixture=False)
    tax = next(t for t in row["treatments"] if t["category"] == "tax")
    assert tax["state"] == "NEEDS_TAX_REVIEW" and tax["allowed_paise"] == 0
    response = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert response.status_code == 200, response.text
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 350000
    with Session(env[0]) as session:
        assert not list(session.scalars(select(NoncashSettlement)))
        assert not list(
            session.scalars(
                select(LedgerLine).where(
                    LedgerLine.account_code.in_(["1310", "1320", "4100", "2110"])
                )
            )
        )


def test_posting_failure_rolls_back_all_financial_effects(documents_environment, monkeypatch):
    import clearledger.finance_posting as service

    env = documents_environment
    _, _, row, _, _ = approved(env)
    before = {p: env[3].get(p).json() for p in ("/invoices", "/receipts")}
    original = service.update_lifecycle

    def failure(*args, **kwargs):
        raise RuntimeError("isolated crash after financial writes")

    monkeypatch.setattr(service, "update_lifecycle", failure)
    with pytest.raises(RuntimeError, match="isolated crash"):
        env[3].post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
    assert {p: env[3].get(p).json() for p in before} == before
    with Session(env[0]) as session:
        assert not list(session.scalars(select(LedgerJournal)))
        assert not list(session.scalars(select(CashAllocation)))
        assert not list(session.scalars(select(NoncashSettlement)))
    monkeypatch.setattr(service, "update_lifecycle", original)
    assert (
        env[3]
        .post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
        .status_code
        == 200
    )


def test_foreign_tenant_and_fabricated_source_are_rejected(documents_environment):
    env = documents_environment
    case, _, row, payload, _ = proposed(env)
    env[4].app.state.finance_identity_verifier = FixtureIdentities(env[2])
    assert (
        env[4].get(f"/journal-proposals/{row['id']}", headers=headers("auditor")).status_code == 404
    )
    assert (
        env[4]
        .post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
        .status_code
        == 404
    )
    payload["source_review_id"] = str(uuid4())
    assert (
        env[3]
        .post(f"/cases/{case['id']}/journal-proposals", json=payload, headers=headers())
        .status_code
        == 404
    )


def test_invalid_transitions_and_stale_approval_version(documents_environment):
    env = documents_environment
    _, _, row, _, _ = proposed(env)
    response = env[3].post(
        f"/journal-proposals/{row['id']}/review",
        headers=headers("controller"),
        json={**command(row), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert response.status_code == 409
    assert (
        env[3]
        .post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
        .status_code
        == 409
    )
    submitted = (
        env[3]
        .post(
            f"/journal-proposals/{row['id']}/request-approval", json=command(row), headers=headers()
        )
        .json()
    )
    response = env[3].post(
        f"/journal-proposals/{row['id']}/review",
        headers=headers("controller"),
        json={**command(row), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert response.status_code == 409
    assert submitted["version"] == row["version"] + 1


def test_bank_recognized_once_across_partial_applications(documents_environment):
    env = documents_environment
    case, _, row, payload, _ = approved(env, tax=False, amount=1000, invoice=1000, apply_amount=500)
    assert (
        env[3]
        .post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
        .status_code
        == 200
    )
    assert env[3].get("/receipts").json()[0]["unapplied_amount_paise"] == 500
    receipt_id = env[3].get("/receipts").json()[0]["id"]
    attest(env[3], receipt_id, "i")
    matched = advanced(env[3], receipt_id, expected_receipt_version=2)
    assert matched.status_code == 200 and matched.json()["outcome"] == "UNIQUE", matched.text
    pump(env)
    current = get(env[3], f"/cases/{case['id']}").json()
    base = {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "matching_proposal_id": matched.json()["id"],
        "cash": [{"invoice_id": payload["cash"][0]["invoice_id"], "amount_paise": 500}],
    }
    review = env[3].post(
        f"/cases/{case['id']}/finance-source-reviews", json=base, headers=headers("controller")
    )
    assert review.status_code == 200, review.text
    second = env[3].post(
        f"/cases/{case['id']}/journal-proposals",
        json={
            **base,
            "policy_id": payload["policy_id"],
            "source_review_id": review.json()["id"],
            "claims": [],
        },
        headers=headers(),
    )
    assert second.status_code == 200, second.text
    assert [j["kind"] for j in second.json()["journals"]] == ["APPLICATION"]
    submitted = (
        env[3]
        .post(
            f"/journal-proposals/{second.json()['id']}/request-approval",
            json=command(second.json()),
            headers=headers(),
        )
        .json()
    )
    checked = env[3].post(
        f"/journal-proposals/{submitted['id']}/review",
        headers=headers("checker"),
        json={**command(submitted), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert checked.status_code == 200, checked.text
    posted = env[3].post(
        f"/journal-proposals/{submitted['id']}/simulate-post",
        json=command(checked.json()),
        headers=headers("poster"),
    )
    assert posted.status_code == 200, posted.text
    with Session(env[0]) as session:
        records = list(session.scalars(select(LedgerJournal)))
        assert [r.kind for r in records].count("BANK") == 1 and len(records) == 3
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 0
    assert env[3].get("/receipts").json()[0]["unapplied_amount_paise"] == 0


def test_reviewed_sales_allowance_requires_verified_promotion(documents_environment):
    env = documents_environment
    case, claims, payload, _ = prepared(env, tax=False, amount=100, invoice=201, category="rebate")
    record = register(env, manifest(env, kind="PROMOTION", category="rebate", value=101))
    assert record.status_code == 200, record.text
    pump(env)
    current = get(env[3], f"/cases/{case['id']}").json()
    payload.update(
        expected_case_version=current["version"], expected_context_sha256=current["context_sha256"]
    )
    review = env[3].post(
        f"/cases/{case['id']}/finance-source-reviews",
        json={
            k: v
            for k, v in payload.items()
            if k
            in {"expected_case_version", "expected_context_sha256", "matching_proposal_id", "cash"}
        },
        headers=headers("controller"),
    )
    assert review.status_code == 200, review.text
    previous = env[3].get("/finance/policies", headers=headers("auditor")).json()[0]
    spec = previous["spec"]
    spec.update(
        version=2,
        previous_id=previous["id"],
        rules=[
            {
                "id": "allowance-test",
                "category": "rebate",
                "treatment": "ALLOWANCE",
                "approved_fixture": True,
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "case_id": case["id"],
                "customer_id": case["customer_id"],
                "receipt_id": env[3].get("/receipts").json()[0]["id"],
                "invoice_id": payload["cash"][0]["invoice_id"],
                "claim_id": claims[0]["id"],
                "amount_paise": 101,
                "required_evidence": [record.json()["id"]],
                "recognition_policy": "REVIEWED_SALES_ALLOWANCE",
            }
        ],
    )
    policy = env[3].post("/finance/policies", json=spec, headers=headers("controller"))
    assert policy.status_code == 200, policy.text
    payload.update(policy_id=policy.json()["id"], source_review_id=review.json()["id"])
    payload["claims"][0]["rule_id"] = "allowance-test"
    row = env[3].post(f"/cases/{case['id']}/journal-proposals", json=payload, headers=headers())
    assert row.status_code == 200, row.text
    assert row.json()["treatments"][0]["allowed_paise"] == 101
    pending = (
        env[3]
        .post(
            f"/journal-proposals/{row.json()['id']}/request-approval",
            json=command(row.json()),
            headers=headers(),
        )
        .json()
    )
    approved_row = (
        env[3]
        .post(
            f"/journal-proposals/{pending['id']}/review",
            headers=headers("controller"),
            json={**command(pending), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
        )
        .json()
    )
    result = env[3].post(
        f"/journal-proposals/{pending['id']}/simulate-post",
        json=command(approved_row),
        headers=headers("poster"),
    )
    assert result.status_code == 200, result.text
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 0
    lines = env[3].get("/finance/journals", headers=headers("auditor")).json()
    assert any(
        line["account_code"] == "4100" and line["debit_paise"] == 101
        for journal in lines
        for line in journal["lines"]
    )


def test_ledger_database_conservation_and_history_are_enforced(documents_environment):
    from sqlalchemy.exc import DBAPIError
    from test_restart_persistence import tenant_rows

    from clearledger.finance_models import (
        AccountBalance,
        FinanceApproval,
        FinanceAudit,
        FinancePolicy,
        FinanceProposalEvent,
    )

    env = documents_environment
    _, _, row, _, _ = approved(env)
    assert (
        env[3]
        .post(
            f"/journal-proposals/{row['id']}/simulate-post",
            json=command(row),
            headers=headers("poster"),
        )
        .status_code
        == 200
    )
    models = (
        LedgerJournal,
        LedgerLine,
        CashAllocation,
        NoncashSettlement,
        AccountBalance,
        FinanceApproval,
        FinanceAudit,
        FinancePolicy,
        FinanceProposalEvent,
        FinanceProposal,
    )
    before = tenant_rows(env[0], env[1], models)
    for model in models:
        with pytest.raises(DBAPIError), env[0].begin() as connection:
            connection.execute(text(f"UPDATE {model.__tablename__} SET version=version+1"))
    for statement in (
        "UPDATE invoices SET open_amount_paise=open_amount_paise+1,version=version+1",
        "UPDATE account_balances SET balance_paise=balance_paise+1,version=version+1",
    ):
        with pytest.raises(DBAPIError), env[0].begin() as connection:
            connection.execute(text(statement))
    assert tenant_rows(env[0], env[1], models) == before


@pytest.mark.parametrize("fault", ["gst", "unknown", "unsigned", "contradiction", "date"])
def test_tax_accounts_and_abstention_are_separate(documents_environment, fault):
    env = documents_environment
    _, _, row, _, _ = approved(
        env,
        tax_kind="GST_TAX" if fault == "gst" else "UNKNOWN" if fault == "unknown" else "INCOME_TAX",
        tax_source_trusted=fault != "unsigned",
        extra_tax_value=99000 if fault == "contradiction" else None,
        tax_rule_date="2026-01-02" if fault == "date" else "2026-01-01",
    )
    treatment = next(t for t in row["treatments"] if t["category"] == "tax")
    assert treatment["allowed_paise"] == (100000 if fault == "gst" else 0)
    if fault != "gst":
        assert treatment["state"] == "NEEDS_TAX_REVIEW"
    response = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert response.status_code == 200, response.text
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == (
        250000 if fault == "gst" else 350000
    )
    with Session(env[0]) as session:
        tax_lines = list(
            session.scalars(
                select(LedgerLine).where(LedgerLine.account_role.in_(["INCOME_TAX", "GST_TAX"]))
            )
        )
        if fault == "gst":
            assert len(tax_lines) == 1 and tax_lines[0].account_code == "1320"
        else:
            assert not tax_lines


def test_concurrent_proposal_requests_have_one_snapshot_and_current_views(documents_environment):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    env = documents_environment
    case, _, payload, _ = prepared(env)
    barrier, key = Barrier(2), uuid4()

    def attempt(_):
        barrier.wait(timeout=10)
        return env[3].post(
            f"/cases/{case['id']}/journal-proposals", json=payload, headers=headers(key=key)
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(attempt, range(2)))
    assert all(r.status_code == 200 for r in rows), [r.text for r in rows]
    assert rows[0].json() == rows[1].json() and not rows[0].json()["is_stale"]


def test_multi_invoice_application_reuses_verified_intent(documents_environment):
    env = documents_environment
    client = env[3]
    client.app.state.finance_identity_verifier = FixtureIdentities(env[1])
    receipt = prepare(client, amounts=(40, 60), cash=100)
    for invoice in ("i", "j"):
        attest(client, receipt, invoice)
    matched = advanced(client, receipt)
    assert matched.status_code == 200 and matched.json()["outcome"] == "UNIQUE", matched.text
    pump(env)
    case = get(client, "/cases").json()[0]
    policy = client.post(
        "/finance/policies",
        headers=headers("controller"),
        json={
            "reference": "multi-invoice",
            "version": 1,
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
        },
    )
    assert policy.status_code == 200, policy.text
    cash = [
        {"invoice_id": i["id"], "amount_paise": i["open_amount_paise"]}
        for i in client.get("/invoices").json()
    ]
    base = {
        "expected_case_version": case["version"],
        "expected_context_sha256": case["context_sha256"],
        "matching_proposal_id": matched.json()["id"],
        "cash": cash,
    }
    review = client.post(
        f"/cases/{case['id']}/finance-source-reviews", headers=headers("controller"), json=base
    )
    assert review.status_code == 200, review.text
    row = client.post(
        f"/cases/{case['id']}/journal-proposals",
        headers=headers(),
        json={**base, "policy_id": policy.json()["id"], "source_review_id": review.json()["id"]},
    )
    assert row.status_code == 200, row.text
    pending = client.post(
        f"/journal-proposals/{row.json()['id']}/request-approval",
        headers=headers(),
        json=command(row.json()),
    ).json()
    checked = client.post(
        f"/journal-proposals/{pending['id']}/review",
        headers=headers("controller"),
        json={**command(pending), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
    )
    assert checked.status_code == 200, checked.text
    posted = client.post(
        f"/journal-proposals/{pending['id']}/simulate-post",
        headers=headers("poster"),
        json=command(checked.json()),
    )
    assert posted.status_code == 200, posted.text
    assert all(i["open_amount_paise"] == 0 for i in client.get("/invoices").json())
