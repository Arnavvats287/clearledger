"""Task-bound review reads never relax the Investigator's verified-customer scope."""

import pytest
from pydantic import SecretStr
from test_correlation_workflow import prepare, tasks
from test_documents import auth
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_finance import FixtureIdentities, headers
from test_restart_persistence import tenant_rows

pytestmark = pytest.mark.postgres


def proof(env, task, actor="auditor", stamp=None):
    return env[3].get(
        f"/review/correlation-tasks/{task['id']}/proof",
        headers=headers(actor),
        params={"expected_task_sha256": stamp or task["input_sha256"]},
    )


def test_pending_proof_can_be_inspected_without_granting_case_identity(documents_environment):
    env = documents_environment
    case, body, _, doc = prepare(env)
    assert case["customer_id"] is None
    task = tasks(env, case)[0]
    before = tenant_rows(env[0], env[1])
    result = proof(env, task)
    assert result.status_code == 200
    assert len(result.json()) == 1
    row = result.json()[0]
    assert row["source_authenticated"] and row["is_current"]
    assert row["citation"]["document_id"] == doc["id"]
    assert row["manifest"]["invoice_id"] == body["invoice_id"]
    assert not row["financial_authority"]
    assert "secret" not in row["manifest"]
    # Existing case tools still require the verified customer relationship.
    old = env[3].get(
        f"/cases/{case['id']}/evidence/records/{row['id']}",
        headers=auth(),
        params={
            "expected_case_version": case["version"],
            "expected_context_sha256": case["context_sha256"],
            "customer_id": body["customer_id"],
        },
    )
    assert old.status_code == 404
    assert tenant_rows(env[0], env[1]) == before


def test_proof_requires_exact_task_snapshot(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    assert proof(env, tasks(env, case)[0], stamp="0" * 64).status_code == 409


def test_proof_cannot_cross_tenant_or_use_actor_labels(documents_environment):
    env = documents_environment
    case, _, _, _ = prepare(env)
    task = tasks(env, case)[0]
    other = FixtureIdentities(env[2])
    other.users["auditor"] = other.users["auditor"].model_copy(
        update={"permissions": frozenset({"REVIEW_READ"})}
    )
    env[4].app.state.finance_identity_verifier = other
    response = env[4].get(
        f"/review/correlation-tasks/{task['id']}/proof",
        headers=headers("auditor"),
        params={"expected_task_sha256": task["input_sha256"]},
    )
    assert response.status_code == 404
    assert (
        env[3]
        .get(
            f"/review/correlation-tasks/{task['id']}/proof",
            headers={**auth(), "X-Actor-ID": "controller"},
            params={"expected_task_sha256": task["input_sha256"]},
        )
        .status_code
        == 401
    )


@pytest.mark.parametrize("signed", [False, True])
def test_unsigned_or_revoked_records_never_become_proof(documents_environment, signed):
    env = documents_environment
    case, _, _, _ = prepare(env, signed=signed)
    task = tasks(env, case)[0]
    if signed:
        env[3].app.state.settings.evidence_trusted_sources_json = SecretStr("[]")
        assert proof(env, task).status_code == 409
    else:
        result = proof(env, task)
        assert result.status_code == 200 and result.json() == []
