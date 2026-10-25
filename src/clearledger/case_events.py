"""Transactional publisher. Metadata events contain IDs, never document instructions."""

from sqlalchemy import select

from clearledger.case_models import DomainEvent, OutboxEvent
from clearledger.matching import digest


def publish(
    session,
    org,
    kind,
    source,
    identifier,
    actor,
    payload=None,
    *,
    key=None,
    case_version=None,
    queued=True,
):
    event_key = digest(key or {"type": kind, "source": source, "id": str(identifier)})
    existing = session.scalar(
        select(DomainEvent).where(
            DomainEvent.organization_id == org, DomainEvent.event_key == event_key
        )
    )
    if existing is not None:
        return existing
    event = DomainEvent(
        organization_id=org,
        event_key=event_key,
        event_type=kind,
        actor_id=actor,
        payload=payload or {},
        case_version=case_version,
        **{source: identifier},
    )
    session.add(event)
    session.flush()
    if queued:
        session.add(OutboxEvent(organization_id=org, event_id=event.id))
    return event


def receipt_accepted(session, receipt, actor):
    return publish(
        session, receipt.organization_id, "receipt.accepted", "receipt_id", receipt.id, actor
    )


def document_changed(session, event):
    return publish(
        session,
        event.organization_id,
        "document.changed",
        "document_event_id",
        event.id,
        event.actor_id,
    )


def matching_proposed(session, proposal, actor):
    return publish(
        session,
        proposal.organization_id,
        "matching.proposed",
        "matching_proposal_id",
        proposal.id,
        actor,
    )


def matching_evidence_registered(session, evidence, actor):
    return publish(
        session,
        evidence.organization_id,
        "matching.evidence_registered",
        "receipt_id",
        evidence.receipt_id,
        actor,
        {"matching_evidence_id": str(evidence.id)},
        key={"evidence": str(evidence.id)},
    )
