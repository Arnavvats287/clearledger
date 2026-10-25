"""Negative security and independent source verification for reviewer operations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_cases import pump
from test_documents import get
from test_evidence import manifest, register
from test_finance import approved, command, headers, prepared
from test_restart_persistence import tenant_rows
from test_review import FINANCIAL, basis, draft_body, local_user, response_body, review, roles
from test_review import documents_environment as documents_environment
from test_review import environment as environment

from clearledger.review_models import ReviewAction, ReviewAudit

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("trusted", [True, False])
def test_draft_delivery_requires_source_authentication_and_citations(
    documents_environment, trusted
):
    env = documents_environment
    case, claims, _, identities = prepared(env, tax=False)
    roles(env, identities)
    result = register(env, manifest(env, kind="WMS", trusted=trusted))
    assert result.status_code == 200, result.text
    pump(env)
    case = get(env[3], f"/cases/{case['id']}").json()
    body = draft_body(env, case, claims)
    body["delivery_record_ids"] = [result.json()["id"]]
    draft = review(env, case, "draft-evidence-request", body)
    if not trusted:
        assert draft.status_code == 409 and "VERIFIED_DELIVERY" in draft.text
    else:
        assert draft.status_code == 200, draft.text
        hit = draft.json()["content"]["sources"]["deliveries"][0]
        assert hit["source_integrity"] and hit["source_authenticated"]
        assert hit["raw_sha256"] and hit["canonical_sha256"] and hit["start"] == 0
        assert hit["metadata"]["facts"]["delivered_quantity"] == 8


def test_request_response_threads_and_immutable_denial_audit(documents_environment):
    env = documents_environment
    case, claims, _, identities = prepared(env, tax=False)
    roles(env, identities)
    body = basis(case, "MISSING_EVIDENCE", claim_ids=[claims[0]["id"]])
    assert review(env, case, "request-evidence", body).status_code == 403
    requested = review(env, case, "request-evidence", body, actor="controller")
    assert requested.status_code == 200, requested.text
    case = get(env[3], f"/cases/{case['id']}").json()
    claims = get(env[3], f"/cases/{case['id']}/claims").json()
    response = review(
        env, case, "record-response", response_body(env, case, claims, requested.json()["id"])
    )
    assert response.status_code == 200, response.text
    audit = env[3].get("/review/audit", headers=headers("auditor")).json()
    assert [a["outcome"] for a in audit] == ["DENIED", "COMPLETED", "COMPLETED"]
    assert audit[0]["code"] == "REVIEW_CONTROLLER_REQUIRED"
    with env[0].connect() as connection:
        for sql in (
            "DELETE FROM review_audit",
            "UPDATE review_actions SET version=2",
            "TRUNCATE review_commands",
        ):
            with pytest.raises(DBAPIError):
                connection.execute(text(sql))
                connection.commit()
            connection.rollback()


def test_concurrent_same_key_response_reuses_one_immutable_action(documents_environment):
    env = documents_environment
    case, claims, _, identities = prepared(env, tax=False)
    roles(env, identities)
    body, key, barrier = response_body(env, case, claims), uuid4(), Barrier(2)

    def call(_):
        barrier.wait()
        return review(env, case, "record-response", body, key=key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    with Session(env[0]) as session:
        assert len(list(session.scalars(select(ReviewAction)))) == 1
        assert len(list(session.scalars(select(ReviewAudit)))) == 1


def test_atomic_response_failure_rolls_back_case_evidence_and_history(
    documents_environment, monkeypatch
):
    env = documents_environment
    case, claims, _, identities = prepared(env, tax=False)
    roles(env, identities)
    body = response_body(env, case, claims)
    before = tenant_rows(env[0], env[1], FINANCIAL)
    from clearledger import review_service
    from clearledger.case_domain import CaseError

    original = review_service.revise

    def fail_after_revision(*args, **kwargs):
        original(*args, **kwargs)
        raise CaseError("TEST_ATOMIC_RESPONSE_FAILURE")

    monkeypatch.setattr(review_service, "revise", fail_after_revision)
    assert review(env, case, "record-response", body).status_code == 409
    assert get(env[3], f"/cases/{case['id']}").json()["version"] == case["version"]
    assert tenant_rows(env[0], env[1], FINANCIAL) == before
    monkeypatch.setattr(review_service, "revise", original)
    assert review(env, case, "record-response", body).status_code == 200


def test_zero_ar_alone_does_not_close_unresolved_mandatory_claim(documents_environment):
    env = documents_environment
    case, _, row, _, identities = approved(env, tax=False, amount=101, invoice=101)
    roles(env, identities)
    result = env[3].post(
        f"/journal-proposals/{row['id']}/simulate-post",
        json=command(row),
        headers=headers("poster"),
    )
    assert result.status_code == 200, result.text
    pump(env)
    case = get(env[3], f"/cases/{case['id']}").json()
    assert env[3].get("/invoices").json()[0]["open_amount_paise"] == 0
    closed = review(env, case, "close", basis(case, "SETTLED_AND_COMPLETE"), actor="controller")
    assert closed.status_code == 409 and "MANDATORY_CLAIMS" in closed.text


def test_local_sessions_reject_remote_client_and_forged_forwarded_loopback(documents_environment):
    env = documents_environment
    credential = local_user(env)
    with TestClient(env[3].app, client=("203.0.113.1", 9876)) as remote:
        result = remote.get("/review/me", headers={**credential, "X-Forwarded-For": "127.0.0.1"})
        assert result.status_code == 403


def test_review_reads_and_foreign_invoice_or_claim_rejected(documents_environment):
    env = documents_environment
    case, claims, _, identities = prepared(env, tax=False)
    roles(env, identities)
    credential = local_user(env, "AUDITOR", "audit")
    assert env[3].get("/review/cases", headers=credential).json()[0]["id"] == case["id"]
    assert env[3].get(f"/review/cases/{case['id']}/claims", headers=credential).status_code == 200
    from test_advanced_matching import advanced, attest, prepare

    foreign_receipt = prepare(env[4], amounts=(101,), cash=101, memo="i")
    attest(env[4], foreign_receipt, "i")
    assert advanced(env[4], foreign_receipt).status_code == 200
    pump((env[0], env[2], env[1], env[4], env[3]))
    foreign_case = get(env[4], "/cases").json()[0]
    assert env[3].get(f"/review/cases/{foreign_case['id']}", headers=credential).status_code == 404
    foreign_invoice = env[4].get("/invoices").json()[0]
    body = draft_body(env, case, claims)
    body["invoice_ids"] = [foreign_invoice["id"]]
    assert review(env, case, "draft-evidence-request", body).status_code == 404
