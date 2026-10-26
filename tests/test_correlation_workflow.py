"""Actual APIs, PostgreSQL and original LangGraph; only synthetic/offline trust roots."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_cases import pump
from test_documents import auth, enable_fake, extract, get, upload
from test_evidence import SOURCE_SECRET, register, sign
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_finance import FixtureIdentities, headers
from test_imports import BANK, post
from test_matching import add_evidence, financial_state, setup

from clearledger.correlation_models import CorrelationDecision
from clearledger.extraction_provider import ProviderReply

pytestmark = pytest.mark.postgres


def prepare(env, *, signed=True, conflict=False, uncertainty="none"):
    client = env[3]
    settings = client.app.state.settings
    settings.case_auto_correlate_extractions = settings.case_auto_investigate_extractions = True
    receipt = setup(client)
    assert add_evidence(client, receipt).status_code == 200
    raw = "CUSTOMER: c\nINVOICE: i\nUTR: t\nAMOUNT: 101 paise\nCLAIM damage: INR 1.01"
    if conflict:
        raw += "\nUTR: other"
    doc = upload(client, raw.encode()).json()

    def span(quote, last=False):
        start = raw.rindex(quote) if last else raw.index(quote)
        return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

    result = {
        "invoice_references": [
            {"value": "i", "span": span("i\n") | {"end": raw.index("i\n") + 1, "quote": "i"}}
        ],
        "utr_references": [
            {"value": "t", "span": span("t\n") | {"end": raw.index("t\n") + 1, "quote": "t"}}
        ],
        "payer_hint": None,
        "claims": [
            {
                "category": "damage",
                "description": span("CLAIM damage: INR 1.01"),
                "amount_paise": 101,
                "amount_span": span("INR 1.01"),
                "reason_code": None,
            }
        ],
        "uncertainty": uncertainty,
        "unparsed_fields": [],
    }
    # Matching offsets survive the unchanged privacy projection; no external provider.
    enable_fake(client, [ProviderReply(json.dumps(result))])
    extracted = extract(client, doc["id"], allow_external=True).json()
    assert extracted["status"] in {"SUCCEEDED", "NEEDS_REVIEW"}, extracted
    customer = client.get("/customers").json()[0]
    invoice = client.get("/invoices").json()[0]
    settings.evidence_trusted_sources_json = SecretStr(
        json.dumps(
            [
                {
                    "organization_id": str(env[1]),
                    "source_system": "test-origin",
                    "key_id": "test-key",
                    "secret": SOURCE_SECRET,
                    "allowed_kinds": ["REMITTANCE"],
                }
            ]
        )
    )
    body = {
        "source_system": "test-origin",
        "source_record_id": "unit-remittance",
        "revision": 1,
        "customer_id": customer["id"],
        "invoice_id": invoice["id"],
        "document_id": doc["id"],
        "document_version": 1,
        "raw_sha256": doc["content_sha256"],
        "canonical_sha256": doc["canonical_sha256"],
        "excerpt": span(raw if not conflict else raw.split("\nUTR: other")[0]),
        "customer_reference": {
            "value": "c",
            "span": span("c\n") | {"end": raw.index("c\n") + 1, "quote": "c"},
        },
        "invoice_reference": {
            "value": "i",
            "span": span("i\n") | {"end": raw.index("i\n") + 1, "quote": "i"},
        },
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
    if signed:
        registered = register(env, sign(env, body))
        assert registered.status_code == 200, registered.text
    if conflict:
        other = {**body, "source_record_id": "unit-conflicting-remittance", "excerpt": span(raw)}
        # The same authenticated excerpt contains two explicit UTRs: it cannot authorize a choice.
        assert register(env, sign(env, other)).status_code == 200
    identities = FixtureIdentities(env[1])
    for name, principal in identities.users.items():
        permissions = {"REVIEW_READ"}
        if name in {"analyst", "controller", "checker"}:
            permissions.add("REVIEW_WORK")
        if name in {"controller", "checker"}:
            permissions.add("REVIEW_CONTROL")
        identities.users[name] = principal.model_copy(
            update={"permissions": frozenset(permissions)}
        )
    client.app.state.finance_identity_verifier = identities  # Test-only; no finance permission.
    pump(env)
    case = next(c for c in get(client, "/cases").json() if doc["id"] in c["document_ids"])
    return case, body, extracted, doc


def tasks(env, case, history=False):
    response = env[3].get(
        f"/review/cases/{case['id']}/correlation-tasks",
        headers=headers("controller"),
        params={"history": str(history).lower()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def decide(env, case, task, decision="CONFIRM", actor="controller", key=None, body=None):
    current = get(env[3], f"/cases/{case['id']}").json()
    payload = body or {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "expected_task_sha256": task["input_sha256"],
        "decision": decision,
    }
    return env[3].post(
        f"/review/correlation-tasks/{task['id']}/decision",
        json=payload,
        headers=headers(actor, key),
    )


@pytest.mark.parametrize("uncertainty", ["none", "review"])
def test_complete_correlated_case_with_evidence_trace_and_nonmutation(
    documents_environment, uncertainty
):
    env = documents_environment
    case, _, extraction, doc = prepare(env, uncertainty=uncertainty)
    before = financial_state(env[3])
    task = tasks(env, case)[0]
    assert task["reason"] == "READY_FOR_REVIEW" and task["status"] == "PENDING"
    response = decide(env, case, task)
    assert response.status_code == 200, response.text
    assert response.json()["financial_authority"] is False
    associations = get(env[3], f"/documents/{doc['id']}/associations")
    assert associations.status_code == 200, associations.text
    assert len(associations.json()) == 1 and not associations.json()[0]["is_stale"]
    pump(env)
    merged = get(env[3], f"/cases/{case['id']}").json()
    assert merged["receipt_ids"] and merged["invoice_ids"] and doc["id"] in merged["document_ids"]
    assert merged["customer_id"] and not merged["is_stale"]
    claims = get(env[3], f"/cases/{merged['id']}/claims").json()
    assert len(claims) == 1 and claims[0]["amount_paise"] == 101
    runs = get(env[3], f"/cases/{merged['id']}/investigations").json()
    current_run = next(r for r in runs if not r["is_stale"])
    findings = get(env[3], f"/investigations/{current_run['id']}/findings").json()
    assert findings[0]["is_current"] and findings[0]["requires_human_review"]
    assert not findings[0]["financial_authority"]
    assert findings[0]["citations"] and findings[0]["source_facts"]
    assert get(env[3], f"/investigations/{current_run['id']}/trace").json()
    assert financial_state(env[3]) == before
    before_runs = len(runs)
    assert pump(env) == {}
    assert len(get(env[3], f"/cases/{merged['id']}/investigations").json()) == before_runs
    assert tasks(env, merged)[0]["status"] == "CONFIRMED"
    assert extraction["financial_authority"] is False


@pytest.mark.parametrize("mode", ["missing", "conflicting", "rejected"])
def test_missing_conflicting_and_rejected_sources_do_not_link(documents_environment, mode):
    env = documents_environment
    case, _, _, _ = prepare(env, signed=mode != "missing", conflict=mode == "conflicting")
    before = financial_state(env[3])
    task = tasks(env, case)[0]
    if mode != "rejected":
        assert task["reason"] != "READY_FOR_REVIEW"
        assert decide(env, case, task).status_code == 409
    response = decide(env, case, task, decision="REJECT")
    assert response.status_code == 200, response.text
    pump(env)
    assert not get(env[3], f"/cases/{case['id']}").json()["receipt_ids"]
    assert tasks(env, case)[0]["status"] == "REJECTED"
    assert pump(env) == {} and len(tasks(env, case, history=True)) == 1
    assert financial_state(env[3]) == before


def test_late_signed_source_refreshes_task_and_review_is_versioned(documents_environment):
    env = documents_environment
    case, body, _, _ = prepare(env, signed=False)
    old = tasks(env, case)[0]
    assert register(env, sign(env, body)).status_code == 200
    pump(env)
    new = tasks(env, case)[0]
    assert new["id"] != old["id"] and new["reason"] == "READY_FOR_REVIEW"
    assert decide(env, case, old).status_code == 409
    assert decide(env, case, new, actor="analyst").status_code == 403
    assert decide(env, case, new, actor="auditor").status_code == 403
    key = uuid4()
    current = get(env[3], f"/cases/{case['id']}").json()
    payload = {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "expected_task_sha256": new["input_sha256"],
        "decision": "CONFIRM",
    }
    response = decide(env, case, new, key=key, body=payload)
    assert response.status_code == 200, response.text
    assert decide(env, case, new, key=key, body=payload).json()["id"] == response.json()["id"]
    assert register(env, sign(env, body)).status_code == 200  # Unchanged source replay.
    pump(env)
    assert len(tasks(env, case, history=True)) == 2


def test_task_history_and_decisions_are_append_only(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    task = tasks(env, case)[0]
    assert decide(env, case, task, decision="REJECT").status_code == 200
    for table in ("correlation_tasks", "correlation_decisions"):
        with Session(env[0]) as session:
            with pytest.raises(DBAPIError):
                session.execute(text(f"DELETE FROM {table}"))
                session.commit()


def test_ambiguous_bank_reference_never_arbitrarily_selects_receipt(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    assert (
        post(
            env[3], "bank-transactions", {**BANK, "account_ref": "second", "memo": "i"}
        ).status_code
        == 200
    )
    pump(env)
    task = tasks(env, case)[0]
    assert task["reason"] == "AMBIGUOUS_RECEIPTS" and len(task["candidates"]) == 2
    assert decide(env, case, task).status_code == 409


def test_concurrent_different_keys_cannot_create_conflicting_decisions(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    task = tasks(env, case)[0]
    before = financial_state(env[3])
    current = get(env[3], f"/cases/{case['id']}").json()
    body = {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "expected_task_sha256": task["input_sha256"],
        "decision": "CONFIRM",
    }
    barrier = Barrier(2)

    def send():
        barrier.wait(timeout=10)
        return decide(env, case, task, body=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: send(), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with Session(env[0]) as session:
        rows = list(
            session.scalars(
                select(CorrelationDecision).where(
                    CorrelationDecision.organization_id == env[1],
                    CorrelationDecision.task_id == UUID(task["id"]),
                )
            )
        )
        assert len(rows) == 1
    assert financial_state(env[3]) == before


def test_revoked_source_key_stales_task_without_authorizing_from_controller_label(
    documents_environment,
):
    env = documents_environment
    case, _, _, _ = prepare(env)
    task = tasks(env, case)[0]
    env[3].app.state.settings.evidence_trusted_sources_json = None
    assert tasks(env, case)[0]["is_stale"]
    assert decide(env, case, task).status_code == 409
    assert not get(env[3], f"/cases/{case['id']}").json()["receipt_ids"]


def test_cross_tenant_and_local_token_do_not_supply_review_authority(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    task = tasks(env, case)[0]
    other = FixtureIdentities(env[2])
    other.users["controller"] = other.users["controller"].model_copy(
        update={"permissions": frozenset({"REVIEW_READ", "REVIEW_CONTROL"})}
    )
    env[4].app.state.finance_identity_verifier = other
    response = env[4].get(
        f"/review/cases/{case['id']}/correlation-tasks", headers=headers("controller")
    )
    assert response.status_code == 404
    current = get(env[3], f"/cases/{case['id']}").json()
    body = {
        "expected_case_version": current["version"],
        "expected_context_sha256": current["context_sha256"],
        "expected_task_sha256": task["input_sha256"],
        "decision": "CONFIRM",
    }
    assert (
        env[3]
        .post(
            f"/review/correlation-tasks/{task['id']}/decision",
            json=body,
            headers={**auth(), "X-Actor-ID": "controller"},
        )
        .status_code
        == 401
    )
    env[3].app.state.finance_identity_verifier = None
    assert (
        env[3]
        .post(f"/review/correlation-tasks/{task['id']}/decision", json=body, headers=auth())
        .status_code
        == 503
    )


def test_additive_migration_roundtrip_preserves_financial_records(documents_environment):
    env = documents_environment
    setup(env[3])
    before = financial_state(env[3])
    cfg = Config("alembic.ini")
    with env[0].connect() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "0011_review")
        command.upgrade(cfg, "head")
        command.check(cfg)
    assert financial_state(env[3]) == before


def test_source_budget_exhaustion_cannot_claim_verified_uniqueness(
    documents_environment, monkeypatch
):
    from clearledger import correlation_sources

    env = documents_environment
    case, _, _, _ = prepare(env)
    monkeypatch.setattr(correlation_sources, "MAX_RECORDS", 0)
    response = env[3].post(
        f"/review/cases/{case['id']}/correlation-tasks/refresh",
        headers=headers("controller"),
        json={},
    )
    assert response.status_code == 200, response.text
    task = response.json()[0]
    assert task["reason"] == "SEARCH_INCOMPLETE"
    assert decide(env, case, task, actor="checker").status_code == 409


def test_legacy_operator_attestation_cannot_bypass_new_review_task(documents_environment):
    env = documents_environment
    case, _, extraction, doc = prepare(env, signed=False)
    receipt = env[3].get("/receipts").json()[0]
    response = env[3].post(
        f"/documents/{doc['id']}/correlate",
        headers=auth(),
        json={
            "extraction_id": extraction["id"],
            "expected_document_version": 1,
            "verified_utr_values": ["t"],
            "expected_receipt_versions": {receipt["id"]: receipt["version"]},
        },
    )
    assert (
        response.status_code == 409 and response.json()["detail"] == "CORRELATION_REVIEW_REQUIRED"
    )
    assert not get(env[3], f"/cases/{case['id']}").json()["receipt_ids"]


def test_manual_correlation_proposer_cannot_confirm_own_task(documents_environment):
    from clearledger.investigation_models import Investigation

    env = documents_environment
    case, body, _, _ = prepare(env, signed=False)
    original = get(env[3], f"/cases/{case['id']}/investigations").json()
    assert len(original) == 1
    assert register(env, sign(env, body)).status_code == 200
    refreshed = env[3].post(
        f"/review/cases/{case['id']}/correlation-tasks/refresh",
        headers=headers("controller"),
        json={},
    )
    assert refreshed.status_code == 200, refreshed.text
    task = refreshed.json()[0]
    assert task["reason"] == "READY_FOR_REVIEW"
    denied = decide(env, case, task)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "CORRELATION_INDEPENDENT_REVIEWER_REQUIRED"
    assert decide(env, case, task, actor="checker").status_code == 200
    pump(env)
    merged = get(env[3], f"/cases/{case['id']}").json()
    # Listing is canonical-case scoped; original merged-case history stays addressable.
    current = get(env[3], f"/cases/{merged['id']}/investigations").json()
    assert len(current) == 1 and not current[0]["is_stale"]
    assert get(env[3], f"/investigations/{original[0]['id']}").json()["is_stale"]
    with Session(env[0]) as session:
        runs = list(
            session.scalars(select(Investigation).where(Investigation.organization_id == env[1]))
        )
        assert len(runs) == 2 and {r.id for r in runs} == {
            UUID(original[0]["id"]),
            UUID(current[0]["id"]),
        }


def test_revised_source_refreshes_investigation_and_unchanged_replay_does_not(
    documents_environment,
):
    env = documents_environment
    case, body, _, _ = prepare(env)
    task = tasks(env, case)[0]
    assert decide(env, case, task).status_code == 200
    pump(env)
    revised = sign(
        env, {**body, "revision": 2, "previous_id": task["candidates"][0]["evidence_ids"][0]}
    )
    assert register(env, revised).status_code == 200
    pump(env)
    fresh = tasks(env, case)[0]
    assert fresh["id"] != task["id"] and fresh["reason"] == "READY_FOR_REVIEW"
    assert decide(env, case, fresh).status_code == 200
    pump(env)
    merged = get(env[3], f"/cases/{case['id']}").json()
    runs = get(env[3], f"/cases/{merged['id']}/investigations").json()
    current = next(r for r in runs if not r["is_stale"])
    finding = get(env[3], f"/investigations/{current['id']}/findings").json()[0]
    assert finding["is_current"] and "STALE_INPUTS" not in finding["unknowns"]
    assert register(env, revised).status_code == 200
    assert pump(env) == {}
    assert len(get(env[3], f"/cases/{merged['id']}/investigations").json()) == len(runs)
