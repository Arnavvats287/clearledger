import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, post
from test_imports import environment as environment
from test_matching import add_evidence, evidence_body, financial_state, headers, match, setup
from test_restart_persistence import tenant_rows

from clearledger import advanced_matching
from clearledger.advanced_domain import Limits, subsets
from clearledger.advanced_matching import create_advanced
from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.main import create_app
from clearledger.matching import lock_company
from clearledger.matching_schemas import AdvancedMatchInput
from clearledger.models import (
    AuditEvent,
    Invoice,
    MatchingEvidence,
    MatchingProposal,
    MatchingRequest,
    Organization,
    Receipt,
)

pytestmark = pytest.mark.postgres


def prepare(client, amounts=(40, 60), cash=100, *, alias=True, memo=None, **invoice_changes):
    assert post(client, "customers", CUSTOMER).status_code == 200
    assert (
        post(
            client,
            "invoices",
            *[
                {
                    **INVOICE,
                    "invoice_number": chr(105 + i),
                    "original_amount_paise": amount,
                    "open_amount_paise": amount,
                    **invoice_changes,
                }
                for i, amount in enumerate(amounts)
            ],
        ).status_code
        == 200
    )
    if alias:
        assert post(client, "payer-aliases", ALIAS).status_code == 200
    assert (
        post(
            client,
            "bank-transactions",
            {
                **BANK,
                "amount_paise": cash,
                "payer_name": "Test Alias",
                "memo": memo
                if memo is not None
                else " ".join(chr(105 + i) for i in range(len(amounts))),
            },
        ).status_code
        == 200
    )
    return client.get("/receipts").json()[0]["id"]


def payload(client, **changes):
    return {
        "expected_receipt_version": 1,
        "expected_invoice_versions": {
            row["id"]: row["version"] for row in client.get("/invoices").json()
        },
        **changes,
    }


def advanced(client, receipt, *, key=None, **changes):
    return client.post(
        f"/receipts/{receipt}/match-advanced", json=payload(client, **changes), headers=headers(key)
    )


def attest(client, receipt, name):
    body = evidence_body(client, invoice_number=name)
    memo = client.get("/bank-transactions").json()[0]["memo"]
    if memo.startswith("{"):
        body["start_offset"] = memo.index(f'"{name}"') + 1
        body["end_offset"] = body["start_offset"] + len(name)
    response = add_evidence(client, receipt, body=body)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("references", [False, True])
def test_unique_multi_invoice_idempotent_history_nonmutation(environment, references):
    engine, org, _, client, other = environment
    receipt = prepare(client)
    if references:
        for name in ("i", "j"):
            attest(client, receipt, name)
    before = tenant_rows(engine, org)
    before_api = financial_state(client)
    context = client.get(f"/receipts/{receipt}/advanced-matching-context").json()
    key = uuid4()
    response = advanced(
        client, receipt, key=key, expected_snapshot_sha256=context["snapshot_sha256"]
    )
    assert response.status_code == 200, response.text
    proposal = response.json()
    result = proposal["result"]
    assert proposal["outcome"] == "UNIQUE"
    assert result["search_exhaustive"] and result["intent_verified"] == references
    assert result["requires_review"]
    assert sorted(a["amount_paise"] for a in result["candidates"][0]["allocations"]) == [40, 60]
    assert proposal["amount_paise"] == 0 and proposal["invoice_id"] is None
    assert not proposal["is_stale"]
    assert (
        advanced(
            client, receipt, key=key, expected_snapshot_sha256=context["snapshot_sha256"]
        ).json()
        == proposal
    )
    assert advanced(client, receipt).json() == proposal
    assert financial_state(client) == before_api
    after = tenant_rows(engine, org)
    for table in before:
        if table != "audit_events":
            assert after[table] == before[table]
    assert all(row in after["audit_events"] for row in before["audit_events"])
    assert len(after["audit_events"]) == len(before["audit_events"]) + 1
    assert client.get(f"/receipts/{receipt}/matches").json() == [proposal]
    assert other.get(f"/matching-proposals/{proposal['id']}").status_code == 404
    assert other.get(f"/receipts/{receipt}/advanced-matching-context").status_code == 404
    assert advanced(other, receipt).status_code == 404
    with engine.connect() as connection:
        for table in ("matching_proposals", "matching_requests", "audit_events"):
            with pytest.raises(DBAPIError):
                connection.execute(text(f"UPDATE {table} SET version=version+1"))
            connection.rollback()


@pytest.mark.parametrize("amounts,count", [((40, 60, 30, 70), 2), ((50, 50, 50), 3)])
def test_competing_subsets_not_arbitrarily_selected(environment, amounts, count):
    _, _, _, client, _ = environment
    receipt = prepare(client, amounts)
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "AMBIGUOUS"
    assert len(proposal["result"]["candidates"]) == count
    assert proposal["result"]["search_exhaustive"]
    assert proposal["invoice_id"] is None and proposal["amount_paise"] == 0


@pytest.mark.parametrize("structured", [False, True])
def test_explicit_partial_keeps_unpaid_ar(environment, structured):
    _, _, _, client, _ = environment
    receipt = prepare(
        client,
        (80, 90) if structured else (150,),
        memo=(json.dumps({"allocations_paise": {"i": 40, "j": 60}}) if structured else "i"),
    )
    for name in ("i", "j") if structured else ("i",):
        attest(client, receipt, name)
    before = financial_state(client)
    response = advanced(client, receipt, use_structured_allocations=structured)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["outcome"] == "UNIQUE" and result["intent_verified"]
    candidate = result["candidates"][0]
    assert candidate["total_paise"] == 100 and candidate["remaining_cash_paise"] == 0
    assert sum(row["remaining_ar_paise"] for row in candidate["allocations"]) == (
        70 if structured else 50
    )
    for allocation in candidate["allocations"]:
        assert allocation["reference_evidence_ids"]
        if structured:
            assert allocation["amount_evidence"]["source_field"] == "memo"
            assert allocation["amount_evidence"]["json_pointer"] in {
                "/allocations_paise/i",
                "/allocations_paise/j",
            }
    assert financial_state(client) == before


@pytest.mark.parametrize(
    "memo,reason",
    [
        ('{"allocations_paise":{"i":40,"j":60}}', "VERIFIED_REFERENCES"),
        ('{"allocations_paise":{"i":40.0,"j":60}}', "INVALID_STRUCTURED_ALLOCATION_EVIDENCE"),
        ('{"allocations_paise":{"i":true,"j":60}}', "INVALID_STRUCTURED_ALLOCATION_EVIDENCE"),
        ('{"allocations_paise":{"i":40,"i":40,"j":60}}', "INVALID_STRUCTURED_ALLOCATION_EVIDENCE"),
        ('{"allocations_paise":{"i":90,"j":10}}', "INVOICE_OVERALLOCATION"),
        ('{"allocations_paise":{"i":30,"j":60}}', "VERIFIED_REFERENCES"),
        ('{"allocations_paise":{"i":70,"j":60}}', "RECEIPT_OVERALLOCATION"),
    ],
)
def test_structured_allocations_are_strict_source_data(environment, memo, reason):
    _, _, _, client, _ = environment
    receipt = prepare(client, (80, 90), memo=memo)
    for name in ("i", "j"):
        attest(client, receipt, name)
    result = advanced(client, receipt, use_structured_allocations=True).json()["result"]
    assert result["reason"] == reason
    assert result["outcome"] == ("UNIQUE" if reason == "VERIFIED_REFERENCES" else "UNRESOLVED")
    if reason == "VERIFIED_REFERENCES":
        candidate = result["candidates"][0]
        supplied = json.loads(memo)["allocations_paise"]
        assert candidate["remaining_cash_paise"] == 100 - sum(supplied.values())


def test_unexplained_partial_and_multi_reference_shortpay_abstain(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client, (80, 90))
    assert advanced(client, receipt).json()["outcome"] == "UNRESOLVED"
    for name in ("i", "j"):
        attest(client, receipt, name)
    result = advanced(client, receipt).json()["result"]
    assert result["outcome"] == "UNRESOLVED" and not result["candidates"]
    assert result["reason"] == "EXPLICIT_ALLOCATION_INSTRUCTIONS_REQUIRED"


def test_partial_possibilities_need_intent(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client, (150, 160))
    result = advanced(client, receipt).json()["result"]
    assert result["outcome"] == "UNRESOLVED" and not result["candidates"]
    assert len(result["partial_analysis"]) == 2 and not result["intent_verified"]


def test_structured_source_amounts_cannot_be_ignored_by_full_balance_mode(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client, (80, 20), memo='{"allocations_paise":{"i":40,"j":10}}')
    for name in ("i", "j"):
        attest(client, receipt, name)
    result = advanced(client, receipt).json()["result"]
    assert result["outcome"] == "UNRESOLVED" and not result["intent_verified"]
    assert result["reason"] == "STRUCTURED_ALLOCATION_MODE_REQUIRED"
    result = advanced(client, receipt, use_structured_allocations=True).json()["result"]
    assert result["outcome"] == "UNIQUE"
    assert result["candidates"][0]["total_paise"] == 50
    assert result["candidates"][0]["remaining_cash_paise"] == 50


@pytest.mark.parametrize(
    "change",
    [
        {"status": "CLOSED", "open_amount_paise": 0},
        {"issued_date": "2027-01-01", "due_date": "2027-01-02"},
    ],
)
def test_ineligible_reference_not_dropped_to_create_false_unique(environment, change):
    engine, org, _, client, _ = environment
    receipt = prepare(client)
    for name in ("i", "j"):
        attest(client, receipt, name)
    with Session(engine) as session:
        invoice = session.scalar(
            select(Invoice).where(Invoice.organization_id == org, Invoice.invoice_number == "i")
        )
        for key, value in change.items():
            if key.endswith("date"):
                from datetime import date

                value = date.fromisoformat(value)
            setattr(invoice, key, value)
        session.commit()
    result = advanced(client, receipt).json()["result"]
    assert result["outcome"] == "UNRESOLVED"
    assert result["reason"] == "INELIGIBLE_REFERENCED_INVOICE"


def test_missing_identity_does_not_guess_and_foreign_expected_ids_rejected(environment):
    _, _, _, client, other = environment
    receipt = prepare(client, alias=False)
    assert advanced(client, receipt).json()["result"]["reason"] == "UNRESOLVED_CUSTOMER"
    foreign = prepare(other)
    invoice = other.get("/invoices").json()[0]
    assert (
        advanced(client, receipt, expected_invoice_versions={invoice["id"]: 1}).status_code == 404
    )
    assert advanced(client, foreign).status_code == 404
    assert (
        add_evidence(
            client,
            receipt,
            **{
                "customer_id": other.get("/customers").json()[0]["id"],
                "invoice_id": invoice["id"],
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize("change", ["balance", "version", "receipt", "evidence", "pool", "limits"])
def test_stale_inputs_preserve_history(environment, change):
    engine, org, _, client, _ = environment
    receipt = prepare(client)
    key = uuid4()
    first = advanced(client, receipt, key=key).json()
    if change == "evidence":
        attest(client, receipt, "i")
    elif change == "pool":
        assert post(client, "invoices", {**INVOICE, "invoice_number": "z"}).status_code == 200
    elif change == "limits":
        client.app.state.settings.matching_limits = Limits(max_work=2000)
    else:
        with Session(engine) as session:
            if change == "receipt":
                row = session.get(Receipt, UUID(receipt))
                row.unapplied_amount_paise = 90
                row.status = "PARTIALLY_APPLIED"
            else:
                row = session.scalar(
                    select(Invoice).where(
                        Invoice.organization_id == org, Invoice.invoice_number == "i"
                    )
                )
                if change == "balance":
                    row.open_amount_paise -= 1
                else:
                    row.version += 1
            session.commit()
    current = client.get(f"/matching-proposals/{first['id']}").json()
    assert current["is_stale"]
    assert current["snapshot"] == first["snapshot"] and current["result"] == first["result"]
    assert advanced(client, receipt, key=key).status_code == 409
    assert (
        advanced(client, receipt, expected_snapshot_sha256=first["snapshot_sha256"]).status_code
        == 409
    )
    assert len(client.get(f"/receipts/{receipt}/matches").json()) == 1


@pytest.mark.parametrize(
    "limits", [Limits(max_candidates=1), Limits(max_work=1), Limits(max_combination_size=1)]
)
def test_configured_limits_persist_incompleteness(environment, limits):
    _, _, _, client, _ = environment
    receipt = prepare(client)
    client.app.state.settings.matching_limits = limits
    response = advanced(client, receipt)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["outcome"] == "SEARCH_INCOMPLETE"
    assert not proposal["result"]["search_exhaustive"] and not proposal["is_stale"]
    assert advanced(client, receipt).json() == proposal


def test_timeout_proposal_replay_does_not_rerun_or_change_result(environment, monkeypatch):
    _, _, _, client, _ = environment
    receipt = prepare(client)
    ticks = iter(range(1000))

    def timed_search(invoices, cash, limits):
        return subsets(invoices, cash, limits, clock=lambda: next(ticks) * 100_000_000)

    monkeypatch.setattr(advanced_matching, "subsets", timed_search)
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "SEARCH_INCOMPLETE"
    assert proposal["result"]["reason"] == "TIME_LIMIT"
    assert not proposal["result"]["search_exhaustive"]

    def must_not_search(*args):
        pytest.fail("A stored snapshot must reuse its immutable search result")

    monkeypatch.setattr(advanced_matching, "subsets", must_not_search)
    assert advanced(client, receipt).json() == proposal


def test_large_eligible_pool_and_closed_invoices_are_bounded(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client)
    # Minimal numeric records exercise the cardinality bound, not an evaluation dataset.
    assert (
        post(
            client,
            "invoices",
            *[
                {
                    **INVOICE,
                    "invoice_number": f"n{i}",
                    "original_amount_paise": 1,
                    "open_amount_paise": 1,
                }
                for i in range(31)
            ],
        ).status_code
        == 200
    )
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "SEARCH_INCOMPLETE"
    assert proposal["result"]["reason"] == "INPUT_LIMIT"
    assert len(proposal["snapshot"]["invoices"]) == 33


def test_integer_bigint_and_existing_partial_balances(environment):
    engine, org, _, client, _ = environment
    receipt = prepare(client, (2**62, 2**62 - 1), cash=2**63 - 1)
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "UNIQUE"
    assert proposal["result"]["candidates"][0]["total_paise"] == 2**63 - 1
    with Session(engine) as session:
        invoices = session.scalars(select(Invoice).where(Invoice.organization_id == org)).all()
        for invoice, amount in zip(
            sorted(invoices, key=lambda row: row.invoice_number), (40, 60), strict=True
        ):
            invoice.open_amount_paise = amount
        record = session.get(Receipt, UUID(receipt))
        record.unapplied_amount_paise = 100
        record.status = "PARTIALLY_APPLIED"
        session.commit()
    before = financial_state(client)
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "UNIQUE"
    assert proposal["result"]["candidates"][0]["total_paise"] == 100
    assert financial_state(client) == before


def test_closed_future_and_other_customer_not_in_subset_pool(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client)
    assert post(client, "customers", {**CUSTOMER, "external_reference": "d"}).status_code == 200
    assert (
        post(
            client,
            "invoices",
            {**INVOICE, "invoice_number": "closed", "open_amount_paise": 0},
            {
                **INVOICE,
                "invoice_number": "future",
                "issued_date": "2027-01-01",
                "due_date": "2027-01-02",
            },
            {**INVOICE, "invoice_number": "foreign-owner", "customer_reference": "d"},
        ).status_code
        == 200
    )
    proposal = advanced(client, receipt).json()
    assert proposal["outcome"] == "UNIQUE"
    assert len(proposal["snapshot"]["invoices"]) == 2


def test_exhausted_receipt_and_invalid_evidence_abstain(environment):
    engine, _, _, client, _ = environment
    receipt = prepare(client)
    attest(client, receipt, "i")
    with Session(engine) as session:
        record = session.get(Receipt, UUID(receipt))
        record.unapplied_amount_paise = 0
        record.status = "FULLY_APPLIED"
        session.commit()
    assert advanced(client, receipt).json()["result"]["reason"] == "NO_AVAILABLE_CASH"
    with Session(engine) as session:
        record = session.get(Receipt, UUID(receipt))
        record.version += 1
        session.commit()
    assert advanced(client, receipt, expected_receipt_version=2).json()["result"]["reason"] == (
        "STALE_OR_INVALID_EVIDENCE"
    )


def test_expected_versions_and_key_conflicts(environment):
    _, _, _, client, _ = environment
    receipt = prepare(client)
    assert advanced(client, receipt, expected_invoice_versions={}).status_code == 409
    assert advanced(client, receipt, expected_receipt_version=2).status_code == 409
    assert advanced(client, receipt, expected_receipt_version=True).status_code == 422
    key = uuid4()
    assert advanced(client, receipt, key=key).status_code == 200
    assert advanced(client, receipt, key=key, use_structured_allocations=True).status_code == 409
    assert (
        client.post(
            f"/receipts/{receipt}/match", json=payload(client), headers=headers(key)
        ).status_code
        == 409
    )


def test_concurrent_distinct_keys_one_snapshot_and_no_mutation(environment):
    engine, org, _, client, _ = environment
    receipt = UUID(prepare(client))
    before = tenant_rows(engine, org)
    body = AdvancedMatchInput(**payload(client))
    barrier = Barrier(2)

    def submit(key):
        with Session(engine) as session:
            pid = session.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            proposal = create_advanced(session, org, receipt, body, key, "tester", Limits())
            return proposal.id, proposal.snapshot_sha256, proposal.result, pid

    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=2) as pool:
        lock_company(blocker, org)
        futures = [pool.submit(submit, uuid4()) for _ in range(2)]
        try:
            deadline = time.monotonic() + 10
            with engine.connect() as observer:
                while True:
                    waiting = observer.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname=current_database() "
                            "AND wait_event_type='Lock' AND wait_event='advisory'"
                        )
                    )
                    observer.rollback()
                    if waiting == 2:
                        break
                    assert time.monotonic() < deadline, "Advanced sessions did not overlap"
                    time.sleep(0.02)
            assert not any(future.done() for future in futures)
        finally:
            blocker.rollback()
        first, second = [future.result(timeout=15) for future in futures]
    assert first[:3] == second[:3] and first[3] != second[3]
    records = tenant_rows(engine, org, (MatchingProposal, MatchingRequest, AuditEvent))
    assert len(records["matching_proposals"]) == 1
    assert len(records["matching_requests"]) == 2
    assert len(records["audit_events"]) == len(before["audit_events"]) + 1
    after = tenant_rows(engine, org)
    for table in before:
        if table != "audit_events":
            assert before[table] == after[table]
    assert all(row in after["audit_events"] for row in before["audit_events"])
    with Session(engine) as session:
        values = {
            key: value
            for key, value in records["matching_proposals"][0].items()
            if key not in {"id", "created_at"}
        }
        session.add(MatchingProposal(**values))
        with pytest.raises(IntegrityError):
            session.commit()


def test_migration_refuses_lossy_history_downgrade(environment, migration_config):
    engine, org, _, client, _ = environment
    receipt = prepare(client)
    advanced(client, receipt)
    before = tenant_rows(engine, org, (MatchingProposal,))
    with engine.connect() as connection:
        migration_config.attributes["connection"] = connection
        with pytest.raises(IntegrityError):
            command.downgrade(migration_config, "0003_exact_matching")
        connection.rollback()
    assert tenant_rows(engine, org, (MatchingProposal,)) == before


def test_upgrade_legacy_history_roundtrip_and_mixed_algorithm_reads(
    disposable_database,
    migration_config,
    monkeypatch,
):
    from clearledger import case_events
    from clearledger.case_models import DomainEvent, OutboxEvent

    url = disposable_database.render_as_string(hide_password=False)
    engine = build_engine(url)
    org = uuid4()
    try:
        with engine.connect() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "0003_exact_matching")
            connection.commit()
        with Session(engine) as session, session.begin():
            session.add(Organization(id=org, name="Test"))
        with TestClient(create_app(Settings(database_url=url, organization_id=org))) as client:
            # Model the actual pre-0007 publisher boundary while constructing
            # legacy rows. Never suppress missing-schema errors in production.
            # Restore every hook before exercising upgraded application behavior.
            with monkeypatch.context() as legacy:
                for publisher in (
                    "receipt_accepted",
                    "matching_evidence_registered",
                    "matching_proposed",
                ):
                    legacy.setattr(case_events, publisher, lambda *args: None)
                receipt = setup(client)
                assert add_evidence(client, receipt).status_code == 200
                exact = match(client, receipt).json()
            assert exact["outcome"] == "EXACT_MATCH"
            models = (
                Invoice,
                Receipt,
                MatchingEvidence,
                MatchingProposal,
                MatchingRequest,
                AuditEvent,
            )
            before = tenant_rows(engine, org, models)
            with engine.connect() as connection:
                migration_config.attributes["connection"] = connection
                command.upgrade(migration_config, "head")
                command.check(migration_config)
                connection.commit()
                command.downgrade(migration_config, "0003_exact_matching")
                connection.commit()
                command.upgrade(migration_config, "head")
                command.check(migration_config)
                connection.commit()
            assert tenant_rows(engine, org, models) == before
            assert client.get(f"/matching-proposals/{exact['id']}").json() == exact
            new = advanced(client, receipt).json()
            with Session(engine) as session:
                published = session.scalar(
                    select(DomainEvent).where(
                        DomainEvent.organization_id == org,
                        DomainEvent.matching_proposal_id == UUID(new["id"]),
                    )
                )
                assert published is not None and published.event_type == "matching.proposed"
                assert (
                    session.scalar(
                        select(OutboxEvent).where(
                            OutboxEvent.organization_id == org,
                            OutboxEvent.event_id == published.id,
                        )
                    )
                    is not None
                )
            assert new["outcome"] == "UNIQUE" and new["result"]["intent_verified"]
            assert {row["id"] for row in client.get(f"/receipts/{receipt}/matches").json()} == {
                exact["id"],
                new["id"],
            }
            assert client.get(f"/matching-proposals/{exact['id']}").json() == exact
    finally:
        engine.dispose()
