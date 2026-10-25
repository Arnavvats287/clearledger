"""Complete operational closure requires already posted exact cash, never a label."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from test_advanced_matching import advanced, attest, prepare
from test_cases import pump
from test_documents import get
from test_finance import FixtureIdentities, command, headers
from test_restart_persistence import tenant_rows
from test_review import FINANCIAL, basis, response_body, review, roles
from test_review import documents_environment as documents_environment
from test_review import environment as environment

pytestmark = pytest.mark.postgres


def fully_paid(env):
    client = env[3]
    identities = roles(env, FixtureIdentities(env[1]))
    client.app.state.finance_identity_verifier = identities
    receipt_id = prepare(client, amounts=(101,), cash=101, memo="i")
    attest(client, receipt_id, "i")
    matching = advanced(client, receipt_id).json()
    pump(env)
    case = get(client, "/cases").json()[0]
    invoice = client.get("/invoices").json()[0]
    base = {
        "expected_case_version": case["version"],
        "expected_context_sha256": case["context_sha256"],
        "matching_proposal_id": matching["id"],
        "cash": [{"invoice_id": invoice["id"], "amount_paise": 101}],
    }
    source = client.post(
        f"/cases/{case['id']}/finance-source-reviews", json=base, headers=headers("controller")
    )
    assert source.status_code == 200, source.text
    policy = client.post(
        "/finance/policies",
        json={
            "reference": "isolated-review-policy",
            "version": 1,
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
            "rules": [],
        },
        headers=headers("controller"),
    )
    assert policy.status_code == 200, policy.text
    proposal = client.post(
        f"/cases/{case['id']}/journal-proposals",
        json={
            **base,
            "policy_id": policy.json()["id"],
            "source_review_id": source.json()["id"],
            "claims": [],
        },
        headers=headers(),
    )
    assert proposal.status_code == 200, proposal.text
    submitted = client.post(
        f"/journal-proposals/{proposal.json()['id']}/request-approval",
        json=command(proposal.json()),
        headers=headers(),
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/journal-proposals/{proposal.json()['id']}/review",
        json={**command(submitted.json()), "decision": "APPROVE", "reason": "VERIFIED_SIMULATION"},
        headers=headers("controller"),
    )
    assert approved.status_code == 200, approved.text
    posted = client.post(
        f"/journal-proposals/{proposal.json()['id']}/simulate-post",
        json=command(approved.json()),
        headers=headers("poster"),
    )
    assert posted.status_code == 200, posted.text
    pump(env)
    return get(client, f"/cases/{case['id']}").json(), identities


def test_close_then_late_customer_response_reopens_without_reversing_ledger(documents_environment):
    env = documents_environment
    case, _ = fully_paid(env)
    assert case["state"] == "PARTIALLY_SETTLED"
    before = tenant_rows(env[0], env[1], FINANCIAL)
    closed = review(env, case, "close", basis(case, "SETTLED_AND_COMPLETE"), actor="controller")
    assert closed.status_code == 200, closed.text
    current = get(env[3], f"/cases/{case['id']}").json()
    assert current["state"] == "CLOSED"
    body = response_body(env, current, [])
    response = review(env, current, "record-response", body)
    assert response.status_code == 200, response.text
    assert get(env[3], f"/cases/{case['id']}").json()["state"] == "INVESTIGATING"
    actions = env[3].get(f"/cases/{case['id']}/review-actions", headers=headers("auditor")).json()
    assert [a["kind"] for a in actions] == ["CLOSE", "RESPONSE"]
    assert actions[0]["is_stale"] is True
    assert tenant_rows(env[0], env[1], FINANCIAL) == before
    pump(env)
    current = get(env[3], f"/cases/{case['id']}").json()
    reclosed = review(
        env, current, "close", basis(current, "SETTLED_AND_COMPLETE"), actor="controller"
    )
    assert reclosed.status_code == 200, reclosed.text
    assert get(env[3], f"/cases/{case['id']}").json()["state"] == "CLOSED"
    assert tenant_rows(env[0], env[1], FINANCIAL) == before


def test_concurrent_closure_cas_and_no_self_closure(documents_environment):
    env = documents_environment
    case, identities = fully_paid(env)
    # Even an entitled controller cannot check their own initiated financial proposal.
    identities.users["analyst"] = identities.users["analyst"].model_copy(
        update={"permissions": identities.users["controller"].permissions}
    )
    assert review(env, case, "close", basis(case, "SETTLED_AND_COMPLETE")).status_code == 403
    barrier = Barrier(2)

    def close(_):
        barrier.wait()
        return review(env, case, "close", basis(case, "SETTLED_AND_COMPLETE"), actor="controller")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(close, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]


def test_closure_rechecks_current_approval_grant(documents_environment):
    env = documents_environment
    case, identities = fully_paid(env)
    identities.users["controller"] = identities.users["controller"].model_copy(
        update={"permissions": identities.users["controller"].permissions - {"APPROVE"}}
    )
    response = review(env, case, "close", basis(case, "SETTLED_AND_COMPLETE"), actor="controller")
    assert response.status_code == 403
