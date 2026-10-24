from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, post
from test_imports import environment as environment

from clearledger.matching import create_proposal, register_evidence
from clearledger.matching_schemas import EvidenceInput, MatchInput
from clearledger.models import (
    AuditEvent,
    MatchingEvidence,
    MatchingProposal,
    MatchingRequest,
)

pytestmark = pytest.mark.postgres


def setup(client, *, alias=True, second=False, **invoice_changes):
    assert post(client, "customers", CUSTOMER).status_code == 200
    assert post(client, "invoices", {**INVOICE, **invoice_changes}).status_code == 200
    if alias:
        assert post(client, "payer-aliases", ALIAS).status_code == 200
    if second:
        assert post(client, "invoices", {**INVOICE, "invoice_number": "j"}).status_code == 200
    assert (
        post(
            client, "bank-transactions", {**BANK, "payer_name": "Test Alias", "memo": "i j"}
        ).status_code
        == 200
    )
    return client.get("/receipts").json()[0]["id"]


def headers(key=None):
    return {"X-Actor-ID": "tester", "Idempotency-Key": str(key or uuid4())}


def evidence_body(client, *, invoice_number="i", kind="INVOICE_REFERENCE"):
    bank = client.get("/bank-transactions").json()[0]
    customer = client.get("/customers").json()[0]
    invoice = next(
        (row for row in client.get("/invoices").json() if row["invoice_number"] == invoice_number),
        None,
    )
    quote = invoice_number if kind == "INVOICE_REFERENCE" else "Test Alias"
    return {
        "kind": kind,
        "customer_id": customer["id"],
        "invoice_id": invoice["id"] if kind == "INVOICE_REFERENCE" else None,
        "expected_receipt_version": client.get("/receipts").json()[0]["version"],
        "expected_customer_version": customer["version"],
        "expected_invoice_version": invoice["version"] if kind == "INVOICE_REFERENCE" else None,
        "source_import_id": bank["source_import_id"],
        "source_row": bank["source_row"],
        "source_field": "memo" if kind == "INVOICE_REFERENCE" else "payer_name",
        "start_offset": bank["memo"].index(quote) if kind == "INVOICE_REFERENCE" else 0,
        "end_offset": bank["memo"].index(quote) + len(quote)
        if kind == "INVOICE_REFERENCE"
        else len(quote),
        "exact_quote": quote,
    }


def add_evidence(client, receipt_id, *, body=None, key=None, **changes):
    payload = evidence_body(client) if body is None else body
    return client.post(
        f"/receipts/{receipt_id}/matching-evidence",
        json={**payload, **changes},
        headers=headers(key),
    )


def match(client, receipt_id, *, key=None, **changes):
    body = {
        "expected_receipt_version": client.get(f"/receipts/{receipt_id}").json().get("version", 1),
        "expected_invoice_versions": {
            row["id"]: row["version"] for row in client.get("/invoices").json()
        },
        **changes,
    }
    return client.post(f"/receipts/{receipt_id}/match", json=body, headers=headers(key))


def financial_state(client):
    return {
        path: client.get(path).json()
        for path in ("/customers", "/invoices", "/bank-transactions", "/receipts", "/payer-aliases")
    }


def test_exact_immutable_idempotent_and_financially_nonmutating(environment):
    engine, org, _, client, _ = environment
    receipt_id = setup(client, second=True)
    initial = financial_state(client)
    evidence_key = uuid4()
    response = add_evidence(client, receipt_id, key=evidence_key)
    assert response.status_code == 200, response.text
    assert add_evidence(client, receipt_id, key=evidence_key).json() == response.json()
    key = uuid4()
    response = match(client, receipt_id, key=key)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["outcome"] == "EXACT_MATCH"
    assert proposal["amount_paise"] == 100
    assert proposal["result"]["invoice_version"] == 1
    assert proposal["result"]["identity"] == "RESOLVED"
    assert not proposal["is_stale"]
    with Session(engine) as session:
        audit_count = session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.organization_id == org)
        )
    assert match(client, receipt_id, key=key).json() == proposal
    assert client.get(f"/matching-proposals/{proposal['id']}").json() == proposal
    assert client.get(f"/receipts/{receipt_id}/matches").json() == [proposal]
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.organization_id == org)
            )
            == audit_count
        )
    assert match(client, receipt_id).json()["id"] == proposal["id"]
    assert financial_state(client) == initial
    # PostgreSQL CHECKs must reject NULL invoice versions as well as negatives.
    with Session(engine) as session:
        original_evidence = session.scalar(
            select(MatchingEvidence).where(MatchingEvidence.organization_id == org)
        )
        values = {
            column.name: getattr(original_evidence, column.name)
            for column in MatchingEvidence.__table__.columns
            if column.name not in ("id", "created_at")
        }
        values.update(invoice_version=None, payload_sha256="f" * 64)
        session.add(MatchingEvidence(**values))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    for table in ("matching_evidence", "matching_proposals", "matching_requests"):
        for sql in (
            f"UPDATE {table} SET version=version+1 WHERE organization_id=:org",
            f"DELETE FROM {table} WHERE organization_id=:org",
            f"TRUNCATE {table} CASCADE",
        ):
            with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    connection.execute(text(sql), {"org": org})
                connection.rollback()


@pytest.mark.parametrize(
    "alias,second,outcome,identity",
    [
        (False, False, "NO_SUPPORTED_MATCH", "UNRESOLVED"),
        (True, False, "NO_SUPPORTED_MATCH", "RESOLVED"),
        (True, True, "AMBIGUOUS", "RESOLVED"),
    ],
)
def test_no_guessing_from_amount_or_payer_name(environment, alias, second, outcome, identity):
    _, _, _, client, _ = environment
    receipt_id = setup(client, alias=alias, second=second)
    initial = financial_state(client)
    result = match(client, receipt_id).json()
    assert result["outcome"] == outcome
    assert result["result"]["identity"] == identity
    assert result["amount_paise"] == 0
    assert financial_state(client) == initial


def test_verified_reference_and_manual_mapping_can_resolve_unknown_payer(environment):
    _, _, _, client, _ = environment
    receipt_id = setup(client, alias=False)
    assert (
        add_evidence(
            client, receipt_id, body=evidence_body(client, kind="CUSTOMER_MAPPING")
        ).status_code
        == 200
    )
    assert match(client, receipt_id).json()["outcome"] == "NO_SUPPORTED_MATCH"
    assert add_evidence(client, receipt_id).status_code == 200
    assert match(client, receipt_id).json()["outcome"] == "EXACT_MATCH"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"open_amount_paise": "0"}, "INVOICE_NOT_OPEN"),
        ({"open_amount_paise": "99"}, "AMOUNT_NOT_EXACT"),
        ({"issued_date": "2027-01-01", "due_date": "2027-01-02"}, "INVOICE_NOT_ISSUED_AT_RECEIPT"),
    ],
)
def test_closed_unequal_future_invoices(environment, changes, reason):
    _, _, _, client, _ = environment
    receipt_id = setup(client, **changes)
    assert add_evidence(client, receipt_id).status_code == 200
    response = match(client, receipt_id)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["reason"] == reason
    assert response.json()["amount_paise"] == 0


@pytest.mark.parametrize(
    "field", ["invoice_version", "invoice_balance", "receipt_version", "receipt_balance"]
)
def test_stale_proposals_including_balances_changed_without_version(environment, field):
    engine, org, _, client, _ = environment
    receipt_id = setup(client)
    assert add_evidence(client, receipt_id).status_code == 200
    key = uuid4()
    original = match(client, receipt_id, key=key).json()
    invoice_id = original["invoice_id"]
    with engine.begin() as connection:
        if field.startswith("invoice"):
            assignment = (
                "version=version+1" if field == "invoice_version" else "open_amount_paise=50"
            )
            connection.execute(
                text(f"UPDATE invoices SET {assignment} WHERE organization_id=:org AND id=:id"),
                {"org": org, "id": UUID(invoice_id)},
            )
        else:
            assignment = (
                "version=version+1"
                if field == "receipt_version"
                else "unapplied_amount_paise=50,status='PARTIALLY_APPLIED'"
            )
            connection.execute(
                text(f"UPDATE receipts SET {assignment} WHERE organization_id=:org AND id=:id"),
                {"org": org, "id": UUID(receipt_id)},
            )
    stale = client.get(f"/matching-proposals/{original['id']}").json()
    assert stale["is_stale"]
    assert stale["snapshot"] == original["snapshot"]
    assert (
        client.post(
            f"/receipts/{receipt_id}/match",
            json={"expected_receipt_version": 1, "expected_invoice_versions": {invoice_id: 1}},
            headers=headers(key),
        ).status_code
        == 409
    )
    assert (
        match(client, receipt_id, expected_snapshot_sha256=original["snapshot_sha256"]).status_code
        == 409
    )


def test_stale_evidence_can_be_reverified_without_overwriting_history(environment):
    engine, org, _, client, _ = environment
    receipt_id = setup(client)
    first = add_evidence(client, receipt_id).json()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE invoices SET version=version+1 WHERE organization_id=:org"), {"org": org}
        )
    assert match(client, receipt_id).json()["result"]["reason"] == "STALE_OR_INVALID_EVIDENCE"
    second = add_evidence(client, receipt_id)
    assert second.status_code == 200, second.text
    assert second.json()["id"] != first["id"]
    assert len(client.get(f"/receipts/{receipt_id}/matching-evidence").json()) == 2
    assert match(client, receipt_id).json()["outcome"] == "EXACT_MATCH"


def test_conflicting_invoice_and_customer_evidence(environment):
    _, _, _, client, _ = environment
    receipt_id = setup(client, second=True)
    assert add_evidence(client, receipt_id).status_code == 200
    assert (
        add_evidence(client, receipt_id, body=evidence_body(client, invoice_number="j")).status_code
        == 200
    )
    assert match(client, receipt_id).json()["result"]["reason"] == "CONFLICTING_INVOICE_REFERENCES"
    assert (
        post(client, "customers", {"external_reference": "other", "name": "Other"}).status_code
        == 200
    )
    other = next(
        row for row in client.get("/customers").json() if row["external_reference"] == "other"
    )
    assert add_evidence(client, receipt_id, customer_id=other["id"]).status_code == 422
    mapping = {**evidence_body(client, kind="CUSTOMER_MAPPING"), "customer_id": other["id"]}
    assert add_evidence(client, receipt_id, body=mapping).status_code == 200
    assert match(client, receipt_id).json()["result"]["reason"] == "CONFLICTING_CUSTOMER_EVIDENCE"


def test_citations_versions_key_conflicts_and_tenant_boundaries(environment):
    engine, org, other_org, client, other = environment
    receipt_id = setup(client)
    for change in (
        {"source_import_id": str(uuid4())},
        {"source_row": 3},
        {"exact_quote": "j"},
        {"start_offset": 2, "end_offset": 3, "exact_quote": "j"},
    ):
        assert add_evidence(client, receipt_id, **change).status_code == 422
    assert add_evidence(client, receipt_id, expected_receipt_version=2).status_code == 409
    assert add_evidence(client, receipt_id, expected_invoice_version=2).status_code == 409
    assert add_evidence(client, receipt_id, expected_customer_version=2).status_code == 409
    key = uuid4()
    evidence = add_evidence(client, receipt_id, key=key).json()
    assert match(client, receipt_id, key=key).status_code == 409
    assert match(client, receipt_id, expected_invoice_versions={}).status_code == 409
    proposal = match(client, receipt_id).json()
    for path in (
        f"/receipts/{receipt_id}/matching-evidence",
        f"/receipts/{receipt_id}/matching-context",
        f"/receipts/{receipt_id}/matches",
        f"/matching-proposals/{proposal['id']}",
    ):
        assert other.get(path).status_code == 404
    assert (
        other.post(
            f"/receipts/{receipt_id}/match", json={"expected_receipt_version": 1}, headers=headers()
        ).status_code
        == 404
    )
    assert (
        other.post(
            f"/receipts/{receipt_id}/matching-evidence",
            json=evidence_body(client),
            headers=headers(),
        ).status_code
        == 404
    )
    with Session(engine) as session:
        session.add(
            MatchingRequest(
                organization_id=other_org,
                receipt_id=UUID(receipt_id),
                idempotency_key=uuid4(),
                request_sha256="0" * 64,
                evidence_id=UUID(evidence["id"]),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_matching_and_evidence_concurrency(environment):
    engine, org, _, client, _ = environment
    receipt_id = UUID(setup(client))
    body = EvidenceInput.model_validate(evidence_body(client))
    evidence_key = uuid4()

    def verify(_):
        with Session(engine) as session:
            return register_evidence(session, org, receipt_id, body, evidence_key, "tester").id

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(verify, range(2)))) == 1
    request = MatchInput(expected_receipt_version=1, expected_invoice_versions={body.invoice_id: 1})
    key = uuid4()

    def propose(_):
        with Session(engine) as session:
            return create_proposal(session, org, receipt_id, request, key, "tester").id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(propose, range(2)))
    assert ids[0] == ids[1]
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(MatchingProposal)
                .where(MatchingProposal.organization_id == org)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(MatchingEvidence)
                .where(MatchingEvidence.organization_id == org)
            )
            == 1
        )


def test_candidate_budget_abstains_and_partial_balances_are_preserved(environment, monkeypatch):
    engine, org, _, client, _ = environment
    receipt_id = setup(client, second=True)
    monkeypatch.setattr("clearledger.matching.INVOICE_BUDGET", 1)
    assert match(client, receipt_id).json()["result"]["reason"] == "AMBIGUOUS_OR_BUDGET_EXCEEDED"
    assert add_evidence(client, receipt_id).status_code == 200
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE invoices SET open_amount_paise=50 "
                "WHERE organization_id=:org AND invoice_number='i'"
            ),
            {"org": org},
        )
        connection.execute(
            text(
                "UPDATE receipts SET unapplied_amount_paise=50,status='PARTIALLY_APPLIED' "
                "WHERE organization_id=:org"
            ),
            {"org": org},
        )
    initial = financial_state(client)
    assert match(client, receipt_id).json()["amount_paise"] == 50
    assert financial_state(client) == initial


def test_verified_invoice_reference_alone_resolves_and_new_evidence_stales(environment):
    _, _, _, client, _ = environment
    receipt_id = setup(client, alias=False)
    assert add_evidence(client, receipt_id).status_code == 200
    original = match(client, receipt_id).json()
    assert original["outcome"] == "EXACT_MATCH"
    assert (
        add_evidence(
            client, receipt_id, body=evidence_body(client, kind="CUSTOMER_MAPPING")
        ).status_code
        == 200
    )
    old = client.get(f"/matching-proposals/{original['id']}").json()
    assert old["is_stale"]
    assert old["result"] == original["result"]
    assert match(client, receipt_id).json()["id"] != original["id"]


def test_source_digest_is_checked_even_if_admin_bypasses_immutability(environment):
    engine, org, _, client, _ = environment
    receipt_id = setup(client)
    assert add_evidence(client, receipt_id).status_code == 200
    original = match(client, receipt_id).json()
    source_id = UUID(client.get("/bank-transactions").json()[0]["source_import_id"])
    # Only the generated disposable DB: simulate corruption by an administrator.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE source_imports DISABLE TRIGGER protect_source_imports")
        )
        connection.execute(
            text(
                "UPDATE source_imports SET raw_bytes = raw_bytes || :suffix "
                "WHERE organization_id=:org AND id=:id"
            ),
            {"org": org, "id": source_id, "suffix": b"tampered"},
        )
        connection.execute(text("ALTER TABLE source_imports ENABLE TRIGGER protect_source_imports"))
    assert client.get(f"/matching-proposals/{original['id']}").json()["is_stale"]
    assert add_evidence(client, receipt_id).status_code == 422
    assert match(client, receipt_id).json()["result"]["reason"] == "STALE_OR_INVALID_EVIDENCE"


def test_transport_span_bounds_and_optimistic_versions(environment):
    _, _, _, client, _ = environment
    receipt_id = setup(client)
    assert (
        add_evidence(
            client, receipt_id, body=evidence_body(client, kind="CUSTOMER_MAPPING"), end_offset=100
        ).status_code
        == 422
    )
    assert add_evidence(client, receipt_id, expected_receipt_version=1.0).status_code == 422
    assert add_evidence(client, receipt_id, organization_id=str(uuid4())).status_code == 422
    assert (
        client.post(
            f"/receipts/{receipt_id}/match", json={"expected_receipt_version": 1}
        ).status_code
        == 422
    )
    assert add_evidence(client, receipt_id).status_code == 200
    assert match(client, receipt_id, expected_invoice_versions={str(uuid4()): 1}).status_code == 404
    assert match(client, receipt_id, expected_receipt_version=2).status_code == 409


def test_different_customers_equal_amount_do_not_change_verified_intent(environment):
    _, _, _, client, _ = environment
    receipt_id = setup(client)
    assert (
        post(client, "customers", {"external_reference": "d", "name": "Other"}).status_code == 200
    )
    assert (
        post(
            client, "invoices", {**INVOICE, "customer_reference": "d", "invoice_number": "other"}
        ).status_code
        == 200
    )
    customer = next(
        row for row in client.get("/customers").json() if row["external_reference"] == "c"
    )
    body = {**evidence_body(client), "customer_id": customer["id"]}
    assert add_evidence(client, receipt_id, body=body).status_code == 200
    result = match(client, receipt_id).json()
    assert result["outcome"] == "EXACT_MATCH"
    assert result["customer_id"] == customer["id"]


def test_future_alias_verification_and_evidence_budget_fail_closed(environment, monkeypatch):
    _, _, _, client, _ = environment
    receipt_id = setup(client, alias=False)
    assert (
        post(client, "payer-aliases", {**ALIAS, "verified_at": "2999-01-01T00:00:00Z"}).status_code
        == 200
    )
    assert match(client, receipt_id).json()["result"]["reason"] == "STALE_OR_INVALID_EVIDENCE"
    assert add_evidence(client, receipt_id).status_code == 200
    monkeypatch.setattr("clearledger.matching.EVIDENCE_BUDGET", 0)
    assert match(client, receipt_id).json()["result"]["reason"] == "AMBIGUOUS_OR_BUDGET_EXCEEDED"
