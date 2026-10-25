"""Transactional case aggregate operations shared by commands and event consumers."""

from uuid import UUID

from clearledger.case_domain import CaseError, CaseState, case_transition, claimed_total
from clearledger.case_events import publish
from clearledger.case_models import (
    Case,
    CaseDocument,
    CaseInvalidation,
    CaseProposal,
    CaseReceipt,
    CaseVersion,
    Claim,
    ClaimVersion,
    Hypothesis,
)
from clearledger.case_repository import group_rows, members, root, scoped
from clearledger.case_sources import current_context
from clearledger.matching import digest


def record(session, org, case, actor, kind, store, details=None, changed_claims=()):
    session.flush()
    context = current_context(session, org, case, store)
    owners = {
        s["decision"]["customers"][0]
        for s in context["receipts"]
        if s["decision"]["identity"] == "RESOLVED" and len(s["decision"]["customers"]) == 1
    }
    owners.update(
        s["posted_customer_id"] for s in context["receipts"] if s.get("posted_customer_id")
    )
    all_known = all(
        s.get("posted_customer_id") or s["decision"]["identity"] == "RESOLVED"
        for s in context["receipts"]
    )
    case.customer_id = UUID(next(iter(owners))) if len(owners) == 1 and all_known else None
    case.context_sha256 = digest(context)
    event = publish(
        session,
        org,
        kind,
        "case_id",
        case.id,
        actor,
        details,
        key={"case": str(case.id), "version": case.version},
        case_version=case.version,
        queued=False,
    )
    claims = group_rows(session, Claim, org, members(session, org, case))
    total, unknown = claimed_total([c.amount_paise for c in claims])
    session.add(
        CaseVersion(
            organization_id=org,
            case_id=case.id,
            case_version=case.version,
            event_id=event.id,
            snapshot={
                "state": case.state,
                "version": case.version,
                "merged_into_id": str(case.merged_into_id) if case.merged_into_id else None,
                "customer_id": str(case.customer_id) if case.customer_id else None,
                "attention_codes": case.attention_codes,
                "context": context,
                "context_sha256": case.context_sha256,
                "claimed_total_paise": total,
                "unknown_amount_count": unknown,
                "verified_settled_paise": settled_claims(session, org, {c.id for c in claims}),
                "financial_authority": False,
                "requires_human_review": True,
            },
        )
    )
    for claim in changed_claims:
        session.add(
            ClaimVersion(
                organization_id=org,
                claim_id=claim.id,
                claim_version=claim.version,
                event_id=event.id,
                snapshot={
                    "state": claim.state,
                    "version": claim.version,
                    "category": claim.category,
                    "amount_paise": claim.amount_paise,
                    "assertion": claim.assertion,
                },
            )
        )
    session.flush()
    return event


def settled_claims(session, org, claim_ids):
    from sqlalchemy import func, select

    from clearledger.finance_models import NoncashSettlement

    total = int(
        session.scalar(
            select(func.coalesce(func.sum(NoncashSettlement.amount_paise), 0)).where(
                NoncashSettlement.organization_id == org, NoncashSettlement.claim_id.in_(claim_ids)
            )
        )
    )

    if total > 2**63 - 1:
        raise CaseError("CASE_SETTLEMENT_TOTAL_OVERFLOW")
    return total


def schedule(session, org, case, event, affected):
    publish(
        session,
        org,
        "case.reevaluation.requested",
        "case_id",
        case.id,
        event.actor_id,
        {"affected_claim_ids": sorted(str(i) for i in affected), "cause_event_id": str(event.id)},
        key={"reevaluate": str(event.id)},
        case_version=case.version,
    )


def revise(
    session,
    org,
    case,
    actor,
    kind,
    store,
    *,
    details=None,
    affected=None,
    changed_claims=(),
    invalidate=True,
    enqueue=True,
    reopen_claims=True,
):
    case.version += 1
    ids = members(session, org, case)
    if affected is None:
        affected = {c.id for c in group_rows(session, Claim, org, ids)}
    changed = {claim.id: claim for claim in changed_claims}
    if invalidate and reopen_claims:
        for claim in group_rows(session, Claim, org, ids):
            if claim.id in affected and claim.state not in {"EXTRACTED", "INVESTIGATING"}:
                claim.state = "INVESTIGATING"
                claim.version += 1
                changed[claim.id] = claim
    if invalidate and case.state in {
        "AWAITING_EVIDENCE",
        "AWAITING_REVIEW",
        "READY_TO_APPLY",
        "PARTIALLY_SETTLED",
        "CLOSED",
    }:
        case_transition(CaseState(case.state), CaseState.INVESTIGATING)
        case.state = "INVESTIGATING"
    event = record(session, org, case, actor, kind, store, details, changed.values())
    if invalidate:
        from clearledger.finance_invalidation import case_changed

        case_changed(session, org, ids, event)
        from clearledger.investigation_service import invalidate as invalidate_investigations

        invalidate_investigations(session, org, case, affected, event)
        targets = [
            ("hypothesis_id", h.id)
            for h in group_rows(session, Hypothesis, org, ids)
            if h.claim_id in affected
        ]
        targets += [("case_proposal_id", p.id) for p in group_rows(session, CaseProposal, org, ids)]
        for field, identifier in targets:
            session.add(
                CaseInvalidation(
                    organization_id=org,
                    case_id=case.id,
                    case_version=case.version,
                    reason=kind,
                    invalidation_key=digest(
                        {
                            "version": case.version,
                            "case": str(case.id),
                            "target": str(identifier),
                            "kind": field,
                        }
                    ),
                    **{field: identifier},
                )
            )
    if enqueue:
        schedule(session, org, case, event, affected)
    return event


def ensure_receipt_case(session, org, receipt, actor, store):
    link = scoped(session, CaseReceipt, org, receipt_id=receipt.id)
    if link:
        return root(session, org, link.case_id)
    case = Case(organization_id=org, state="NEW")
    session.add(case)
    session.flush()
    session.add(CaseReceipt(organization_id=org, case_id=case.id, receipt_id=receipt.id))
    event = record(session, org, case, actor, "case.opened", store)
    schedule(session, org, case, event, set())
    return case


def ensure_document_case(session, org, document, actor, store):
    link = scoped(session, CaseDocument, org, document_id=document.id)
    if link:
        return root(session, org, link.case_id)
    case = Case(organization_id=org, state="NEW")
    session.add(case)
    session.flush()
    session.add(CaseDocument(organization_id=org, case_id=case.id, document_id=document.id))
    record(session, org, case, actor, "case.opened", store)
    return case


def merge(session, org, source, target, actor, store, association_id):
    source, target = root(session, org, source.id), root(session, org, target.id)
    if source.id == target.id:
        return target
    if len(members(session, org, source) | members(session, org, target)) > 256:
        raise CaseError("CASE_MEMBERSHIP_LIMIT")
    owners = []
    for case in (source, target):
        context = current_context(session, org, case, store)
        owners.append({i for snap in context["receipts"] for i in snap["decision"]["customers"]})
    if owners[0] and owners[1] and owners[0] != owners[1]:
        for case in (source, target):
            if "CONFLICTING_CUSTOMER_SOURCES" not in case.attention_codes:
                case.attention_codes = [*case.attention_codes, "CONFLICTING_CUSTOMER_SOURCES"]
            revise(
                session,
                org,
                case,
                actor,
                "case.source_conflict",
                store,
                details={
                    "association_id": str(association_id),
                    "other_case_id": str(target.id if case.id == source.id else source.id),
                },
            )
        return source
    source.merged_into_id = target.id
    revise(
        session,
        org,
        source,
        actor,
        "case.merged",
        store,
        details={"canonical_case_id": str(target.id)},
        invalidate=True,
        enqueue=False,
    )
    revise(
        session,
        org,
        target,
        actor,
        "case.sources_merged",
        store,
        details={"historical_case_id": str(source.id), "association_id": str(association_id)},
    )
    return target
