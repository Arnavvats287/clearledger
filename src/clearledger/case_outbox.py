"""Leased PostgreSQL delivery: at-least-once transport, transactional deduped effects."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError, retry_seconds
from clearledger.case_models import DomainEvent, EventConsumption, OutboxDelivery, OutboxEvent
from clearledger.case_processing import consume
from clearledger.case_repository import scoped
from clearledger.document_contract import ExtractionError
from clearledger.document_runtime import LocalOriginals
from clearledger.matching import lock_company, owned

CONSUMER = "case-lifecycle-v1"


def claim_one(engine, org, settings):
    with Session(engine) as session, session.begin():
        now = session.scalar(text("SELECT clock_timestamp()"))
        row = session.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.organization_id == org,
                or_(
                    and_(
                        OutboxEvent.status.in_(["PENDING", "RETRY"]),
                        OutboxEvent.available_at <= now,
                    ),
                    and_(OutboxEvent.status == "LEASED", OutboxEvent.lease_until <= now),
                ),
            )
            .order_by(OutboxEvent.available_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        if row.status == "LEASED":
            session.add(
                OutboxDelivery(
                    organization_id=org,
                    outbox_id=row.id,
                    attempt=row.attempts,
                    phase="EXPIRED",
                    error_code="LEASE_EXPIRED",
                )
            )
        if row.attempts >= settings.case_outbox_max_attempts:
            row.status = "DEAD"
            row.lease_token = row.lease_until = None
            row.last_error_code = "ATTEMPT_BUDGET_EXHAUSTED"
            row.version += 1
            return (row.id, None)
        row.attempts += 1
        row.version += 1
        row.status = "LEASED"
        row.lease_token = uuid4()
        row.lease_until = now + timedelta(seconds=settings.case_outbox_lease_seconds)
        session.add(
            OutboxDelivery(
                organization_id=org,
                outbox_id=row.id,
                attempt=row.attempts,
                phase="CLAIMED",
                error_code=None,
            )
        )
        session.flush()
        return row.id, row.lease_token


def deliver(engine, org, identifier, token, settings):
    if token is None:
        return "DEAD"
    try:
        with Session(engine) as inspection:
            event = inspection.scalar(
                select(DomainEvent)
                .join(OutboxEvent, OutboxEvent.event_id == DomainEvent.id)
                .where(
                    OutboxEvent.organization_id == org,
                    DomainEvent.organization_id == org,
                    OutboxEvent.id == identifier,
                )
            )
            if event is not None and event.event_type == "investigation.requested":
                from uuid import UUID

                from clearledger.investigation_graph import execute
                from clearledger.investigation_runtime import Runtime

                run_id = UUID(event.payload["run_id"])
            else:
                run_id = None
        if run_id:
            return execute(Runtime(engine, org, run_id, identifier, token, settings))
        with Session(engine) as session, session.begin():
            lock_company(session, org)
            row = session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.organization_id == org, OutboxEvent.id == identifier)
                .with_for_update()
            )
            now = session.scalar(text("SELECT clock_timestamp()"))
            if (
                row is None
                or row.status != "LEASED"
                or row.lease_token != token
                or row.lease_until <= now
            ):
                return "SUPERSEDED"
            event = owned(session, DomainEvent, org, row.event_id)
            if scoped(session, EventConsumption, org, event_id=event.id, consumer=CONSUMER) is None:
                result = consume(
                    session, org, event, settings, LocalOriginals(settings.document_root)
                )
                session.add(
                    EventConsumption(
                        organization_id=org,
                        event_id=event.id,
                        consumer=CONSUMER,
                        outcome="HANDLED" if result else "NO_ACTION",
                    )
                )
            row.status = "DELIVERED"
            row.lease_token = row.lease_until = None
            row.last_error_code = None
            row.version += 1
            session.add(
                OutboxDelivery(
                    organization_id=org,
                    outbox_id=row.id,
                    attempt=row.attempts,
                    phase="DELIVERED",
                    error_code=None,
                )
            )
        return "DELIVERED"
    except Exception as error:
        code = (
            error.code
            if isinstance(error, CaseError)
            else str(error)
            if isinstance(error, ExtractionError)
            else "CASE_EVENT_FAILED"
        )
        # Never retain SQL/provider/request exception diagnostics or source content.
        if code not in {
            "CASE_ANALYSIS_LIMIT",
            "CASE_MEMBERSHIP_LIMIT",
            "CASE_GRAPH_LIMIT",
            "DOCUMENT_INTEGRITY_FAILURE",
            "ORIGINAL_NOT_FOUND",
        }:
            code = "CASE_EVENT_FAILED"
        with Session(engine) as session, session.begin():
            lock_company(session, org)
            row = session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.organization_id == org, OutboxEvent.id == identifier)
                .with_for_update()
            )
            if row is None or row.status != "LEASED" or row.lease_token != token:
                return "SUPERSEDED"
            row.status = "DEAD" if row.attempts >= settings.case_outbox_max_attempts else "RETRY"
            row.available_at = session.scalar(text("SELECT clock_timestamp()")) + timedelta(
                seconds=retry_seconds(row.attempts)
            )
            row.lease_token = row.lease_until = None
            row.last_error_code = code
            row.version += 1
            session.add(
                OutboxDelivery(
                    organization_id=org,
                    outbox_id=row.id,
                    attempt=row.attempts,
                    phase="FAILED",
                    error_code=code,
                )
            )
            outcome = row.status
        return outcome


def drain(engine, org, settings, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid delivery budget")
    result = {}
    for _ in range(limit):
        claimed = claim_one(engine, org, settings)
        if claimed is None:
            break
        outcome = deliver(engine, org, *claimed, settings)
        result[outcome] = result.get(outcome, 0) + 1
    return result
