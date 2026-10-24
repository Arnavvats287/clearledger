"""G3: overlapping different-key PostgreSQL sessions, not sequential imitations."""

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_imports import environment as environment
from test_matching import add_evidence, evidence_body, financial_state, setup
from test_restart_persistence import tenant_rows

from clearledger.matching import create_proposal, lock_company
from clearledger.matching_schemas import MatchInput
from clearledger.models import (
    AuditEvent,
    BankTransaction,
    Customer,
    Invoice,
    MatchingEvidence,
    MatchingProposal,
    MatchingRequest,
    PayerAlias,
    Receipt,
    SourceImport,
)

pytestmark = pytest.mark.postgres


def test_different_keys_contend_and_reuse_one_immutable_snapshot(environment):
    engine, organization_id, _, client, _ = environment
    receipt_id = UUID(setup(client))
    assert add_evidence(client, receipt_id).status_code == 200
    body = evidence_body(client)
    request = MatchInput(
        expected_receipt_version=1, expected_invoice_versions={UUID(body["invoice_id"]): 1}
    )
    keys = (uuid4(), uuid4())
    financial_models = (Customer, Invoice, BankTransaction, Receipt, PayerAlias, SourceImport)
    before = tenant_rows(engine, organization_id, financial_models)
    before_api = financial_state(client)
    history = tenant_rows(engine, organization_id, (AuditEvent, MatchingEvidence))
    barrier, sessions = Barrier(3), Queue()

    def submit(key):
        with Session(engine) as session:
            pid = session.scalar(text("SELECT pg_backend_pid()"))
            isolation = session.scalar(text("SHOW transaction_isolation"))
            sessions.put((pid, isolation))
            barrier.wait(timeout=15)
            proposal = create_proposal(session, organization_id, receipt_id, request, key, "tester")
            return proposal.id, proposal.snapshot_sha256, proposal.result, pid

    # Deliberately hold the real PostgreSQL company lock until both workers are
    # observed waiting on it. This proves simultaneous live sessions/contention.
    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=2) as pool:
        lock_company(blocker, organization_id)
        futures = [pool.submit(submit, key) for key in keys]
        try:
            pid_records = [sessions.get(timeout=15) for _ in keys]
            assert len({pid for pid, _ in pid_records}) == 2
            assert {level for _, level in pid_records} == {"read committed"}
            barrier.wait(timeout=15)
            deadline = time.monotonic() + 10
            with engine.connect() as observer:
                while True:
                    waiting = (
                        observer.execute(
                            text(
                                "SELECT pid FROM pg_stat_activity WHERE pid IN (:a,:b) "
                                "AND wait_event_type='Lock' AND wait_event='advisory'"
                            ),
                            {"a": pid_records[0][0], "b": pid_records[1][0]},
                        )
                        .scalars()
                        .all()
                    )
                    # Clear the monitoring transaction's statistics snapshot.
                    observer.rollback()
                    if set(waiting) == {pid for pid, _ in pid_records}:
                        break
                    assert time.monotonic() < deadline, (
                        "Workers did not overlap at the company lock"
                    )
                    time.sleep(0.02)
            assert not any(future.done() for future in futures)
        finally:
            blocker.rollback()
        results = [future.result(timeout=20) for future in futures]

    assert results[0][:3] == results[1][:3]
    assert results[0][3] != results[1][3]
    proposal_id, snapshot_hash, decision, _ = results[0]
    assert decision["outcome"] == "EXACT_MATCH"
    assert decision["amount_paise"] == 100
    assert tenant_rows(engine, organization_id, financial_models) == before
    assert financial_state(client) == before_api
    records = tenant_rows(
        engine, organization_id, (MatchingProposal, MatchingRequest, AuditEvent, MatchingEvidence)
    )
    assert len(records["matching_proposals"]) == 1
    proposal = records["matching_proposals"][0]
    assert proposal["id"] == proposal_id and proposal["snapshot_sha256"] == snapshot_hash
    assert proposal["snapshot"]["receipt"]["unapplied_amount_paise"] == 100
    requests = [row for row in records["matching_requests"] if row["proposal_id"] is not None]
    assert len(requests) == 2
    assert {row["idempotency_key"] for row in requests} == set(keys)
    assert {row["proposal_id"] for row in requests} == {proposal_id}
    assert len({row["request_sha256"] for row in requests}) == 1
    assert records["matching_evidence"] == history["matching_evidence"]
    old_events = {row["id"]: row for row in history["audit_events"]}
    new_events = {row["id"]: row for row in records["audit_events"]}
    assert all(new_events[key] == value for key, value in old_events.items())
    created = [row for key, row in new_events.items() if key not in old_events]
    assert len(created) == 1
    assert created[0]["event_type"] == "matching.proposal_created"
    assert created[0]["entity_id"] == proposal_id
    assert created[0]["source_import_id"] == before["bank_transactions"][0]["source_import_id"]

    # Replays preserve both immutable request mappings and all audit/proposal rows.
    for key in keys:
        with Session(engine) as session:
            assert (
                create_proposal(session, organization_id, receipt_id, request, key, "tester").id
                == proposal_id
            )
    assert (
        tenant_rows(
            engine,
            organization_id,
            (MatchingProposal, MatchingRequest, AuditEvent, MatchingEvidence),
        )
        == records
    )
    with Session(engine) as session:
        values = {
            column.name: proposal[column.name]
            for column in MatchingProposal.__table__.columns
            if column.name not in ("id", "created_at")
        }
        session.add(MatchingProposal(**values))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    for table in ("matching_proposals", "matching_requests", "audit_events"):
        with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(f"UPDATE {table} SET version=version+1 WHERE organization_id=:org"),
                    {"org": organization_id},
                )
            connection.rollback()
    assert tenant_rows(engine, organization_id, financial_models) == before
    assert (
        tenant_rows(
            engine,
            organization_id,
            (MatchingProposal, MatchingRequest, AuditEvent, MatchingEvidence),
        )
        == records
    )
