"""Whole-app role mode prevents bypass through older source/import APIs."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_documents import auth
from test_imports import CUSTOMER, csv_bytes, post
from test_restart_persistence import tenant_rows
from test_review import FINANCIAL, local_user
from test_review import documents_environment as documents_environment
from test_review import environment as environment

from clearledger.models import AuditEvent
from clearledger.review_models import ReviewAudit

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    "path",
    [
        "/imports/customers",
        "/documents",
        "/cases/reconcile",
        "/evidence/records",
        "/receipts/invalid/match",
    ],
)
def test_auditor_cannot_bypass_role_checks_via_legacy_mutation_routes(documents_environment, path):
    env = documents_environment
    credential = local_user(env, "AUDITOR", "auditor")
    before = tenant_rows(env[0], env[1], FINANCIAL)
    result = env[3].post(path, json={}, headers={**credential, "X-Actor-ID": "CONTROLLER"})
    assert result.status_code == 403 and "REVIEW_READ_ONLY" in result.text
    # Dropping the session or substituting the old service token is not a bypass.
    assert env[3].post(path, json={}, headers={"Authorization": ""}).status_code in {401, 503}
    assert env[3].post(path, json={}, headers=auth()).status_code in {401, 503}
    assert tenant_rows(env[0], env[1], FINANCIAL) == before


def test_analyst_import_and_document_auth_are_canonical_and_audited(documents_environment):
    env = documents_environment
    credential = local_user(env)
    imported = post(env[3], "customers", CUSTOMER)
    assert imported.status_code == 200, imported.text
    document = env[3].post(
        "/documents",
        content=b"INVOICE: i",
        headers={
            **credential,
            "Content-Type": "text/plain",
            "X-Source-Filename": "isolated.txt",
            "X-Synthetic-Data": "true",
            "Idempotency-Key": str(uuid4()),
            "X-Actor-ID": "CONTROLLER",
        },
    )
    assert document.status_code == 200, document.text
    assert env[3].get("/documents", headers=credential).status_code == 200
    assert env[3].get("/customers", headers=credential).status_code == 200
    assert env[3].get("/customers", headers={"Authorization": ""}).status_code in {401, 503}
    with Session(env[0]) as session:
        events = list(
            session.scalars(select(ReviewAudit).where(ReviewAudit.operation == "LEGACY_WRITE"))
        )
        assert len(events) == 2 and all(e.actor["authority"] == "LOCAL_DEMO_ONLY" for e in events)
        old = session.scalar(select(AuditEvent))
        assert old.actor_id.startswith("review.") and old.actor_id != "CONTROLLER"


def test_explicit_role_mode_fails_closed_without_verified_or_demo_identity(documents_environment):
    env = documents_environment
    env[3].app.state.settings.review_access_enabled = True
    assert env[3].get("/health").status_code == 200
    assert env[3].get("/ready").status_code == 200
    result = env[3].post(
        "/imports/customers",
        content=csv_bytes("customers", CUSTOMER),
        headers={**auth(), "Content-Type": "text/csv"},
    )
    assert result.status_code == 503
    assert env[3].get("/customers").status_code == 503


def test_auditor_evidence_post_query_remains_database_readonly(documents_environment):
    from test_finance import prepared

    env = documents_environment
    case, _, _, _ = prepared(env, tax=False)
    credential = local_user(env, "AUDITOR", "auditor")
    before = tenant_rows(env[0], env[1], FINANCIAL)
    body = {
        "expected_case_version": case["version"],
        "expected_context_sha256": case["context_sha256"],
        "customer_id": case["customer_id"],
        "tool": "get_invoice_evidence",
    }
    result = env[3].post(f"/cases/{case['id']}/evidence/search", json=body, headers=credential)
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["source_integrity"] is True
    assert tenant_rows(env[0], env[1], FINANCIAL) == before


def test_role_mode_does_not_lift_old_financial_state_capabilities(documents_environment):
    from test_finance import prepared

    env = documents_environment
    case, _, _, _ = prepared(env, tax=False)
    credential = local_user(env, "CONTROLLER", "controller")
    before = tenant_rows(env[0], env[1], FINANCIAL)
    investigated = env[3].post(
        f"/cases/{case['id']}/investigate",
        json={"expected_case_version": case["version"]},
        headers={**credential, "Idempotency-Key": str(uuid4())},
    )
    assert investigated.status_code == 200, investigated.text
    result = env[3].post(
        f"/cases/{case['id']}/transition",
        json={"expected_case_version": investigated.json()["version"], "target": "READY_TO_APPLY"},
        headers={**credential, "Idempotency-Key": str(uuid4()), "X-Actor-ID": "system"},
    )
    assert result.status_code == 403 and "CAPABILITY_REQUIRED" in result.text, result.text
    assert tenant_rows(env[0], env[1], FINANCIAL) == before
