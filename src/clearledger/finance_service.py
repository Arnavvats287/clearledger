"""Trusted financial commands. Evidence preflight is read-only, writes are serialized."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.finance_contract import Journal, ProposalInput, ProposalView, Treatment
from clearledger.finance_domain import EDGES, transition
from clearledger.finance_models import (
    FinanceApproval,
    FinancePolicy,
    FinanceProposal,
    FinanceSourceReview,
)
from clearledger.finance_repository import (
    audit,
    base,
    check_identity,
    fingerprint,
    history,
    policy,
    remember,
    replay,
)
from clearledger.finance_validation import compare_locked, evaluate
from clearledger.matching import digest, lock_company, owned


def view(session, org, row, settings):
    try:
        preflight, _, _ = evaluate(
            session.get_bind(),
            org,
            row.case_id,
            ProposalInput.model_validate(row.snapshot["body"]),
            settings,
        )
        stale = digest(preflight) != row.snapshot_sha256
    except Exception:
        stale = True
    if row.state == "SIMULATED_POSTED":
        stale = False  # This is immutable execution history, not a reusable approval.
    elif row.state == "APPROVED":
        from clearledger.case_repository import scoped

        approval = scoped(session, FinanceApproval, org, proposal_id=row.id)
        stale |= approval is None or approval.expires_at <= datetime.now(UTC)
    return ProposalView(
        id=row.id,
        case_id=row.case_id,
        receipt_id=row.receipt_id,
        policy_id=row.policy_id,
        version=row.version,
        state=row.state,
        snapshot_sha256=row.snapshot_sha256,
        journals=[Journal.model_validate(j) for j in row.journals],
        treatments=[Treatment.model_validate(t) for t in row.treatments],
        is_stale=stale,
    )


def publish_policy(session, org, body, key, principal):
    principal.require("REVIEW_POLICY", org)
    if any(rule.category == "tax" for rule in body.rules):
        principal.require("REVIEW_TAX_POLICY", org)
    lock_company(session, org)
    stamp = fingerprint("POLICY", org, body, principal)
    previous_result = replay(session, org, key, stamp)
    if previous_result:
        return previous_result
    previous = session.scalar(
        select(FinancePolicy)
        .where(FinancePolicy.organization_id == org, FinancePolicy.reference == body.reference)
        .order_by(FinancePolicy.policy_version.desc())
        .limit(1)
    )
    if (previous is None and body.version != 1) or (
        previous is not None
        and (body.previous_id != previous.id or body.version != previous.policy_version + 1)
    ):
        raise CaseError("POLICY_VERSION_CONFLICT")
    from clearledger.finance_models import LedgerLine

    for role, account in body.chart.model_dump().items():
        conflict = session.scalar(
            select(LedgerLine.id)
            .where(
                LedgerLine.organization_id == org,
                LedgerLine.account_code == account,
                LedgerLine.account_role != role,
            )
            .limit(1)
        )
        if conflict:
            raise CaseError("ACCOUNT_ROLE_MIGRATION_REQUIRED")
    record = FinancePolicy(
        organization_id=org,
        reference=body.reference,
        policy_version=body.version,
        previous_id=body.previous_id,
        spec=body.model_dump(mode="json"),
        content_sha256=digest(body.model_dump(mode="json")),
        reviewer=principal.provenance(),
    )
    session.add(record)
    session.flush()
    result = {
        "id": str(record.id),
        "version": record.policy_version,
        "content_sha256": record.content_sha256,
        "simulation_only": True,
        "legal_authority": False,
    }
    remember(session, org, key, stamp, "POLICY", result, principal)
    audit(session, org, principal, "finance.policy_reviewed", policy_id=record.id)
    if previous is not None:
        from clearledger.finance_invalidation import ACTIVE, invalidate_rows

        old = list(
            session.scalars(
                select(FinanceProposal).where(
                    FinanceProposal.organization_id == org,
                    FinanceProposal.policy_id == previous.id,
                    FinanceProposal.state.in_(ACTIVE),
                )
            )
        )
        invalidate_rows(session, org, old, principal.provenance(), "POLICY_SUPERSEDED")
    session.commit()
    return result


def review_sources(session, org, case_id, body, key, principal, settings):
    principal.require("REVIEW_SOURCES", org)
    lock_company(session, org)
    stamp = fingerprint("SOURCE_REVIEW", case_id, body, principal)
    previous = replay(session, org, key, stamp)
    if previous:
        return previous
    case, receipt, _, _, inputs = base(session, org, case_id, body, settings)
    record = FinanceSourceReview(
        organization_id=org,
        case_id=case.id,
        receipt_id=receipt.id,
        customer_id=case.customer_id,
        matching_proposal_id=body.matching_proposal_id,
        snapshot=inputs,
        snapshot_sha256=digest(inputs),
        reviewer=principal.provenance(),
        expires_at=min(principal.expires_at, datetime.now(UTC) + timedelta(hours=1)),
    )
    session.add(record)
    session.flush()
    result = {
        "id": str(record.id),
        "source_snapshot_sha256": record.snapshot_sha256,
        "expires_at": record.expires_at.isoformat(),
        "simulation_only": True,
    }
    remember(session, org, key, stamp, "SOURCE_REVIEW", result, principal)
    audit(session, org, principal, "finance.sources_reviewed", source_review_id=record.id)
    session.commit()
    return result


def authorities(session, org, row, verifier):
    record, spec = policy(session, org, row.policy_id)
    check_identity(verifier, record.reviewer, "REVIEW_POLICY", org)
    if any(r.category == "tax" for r in spec.rules):
        check_identity(verifier, record.reviewer, "REVIEW_TAX_POLICY", org)
    review = owned(session, FinanceSourceReview, org, row.source_review_id)
    check_identity(verifier, review.reviewer, "REVIEW_SOURCES", org)
    if review.expires_at <= datetime.now(UTC):
        raise CaseError("SOURCE_REVIEW_EXPIRED")
    return spec


def create(session, org, case_id, body, key, principal, settings, verifier):
    principal.require("PROPOSE", org)
    stamp = fingerprint("PROPOSE", case_id, body, principal)
    previous = replay(session, org, key, stamp)
    if previous:
        row = owned(session, FinanceProposal, org, UUID(previous["id"]))
        session.commit()
        return row
    snapshot, journals, treatments = evaluate(session.get_bind(), org, case_id, body, settings)
    lock_company(session, org)
    previous = replay(session, org, key, stamp)
    if previous:
        row = owned(session, FinanceProposal, org, UUID(previous["id"]))
        session.commit()
        return row
    checksum = digest(snapshot)
    row = session.scalar(
        select(FinanceProposal).where(
            FinanceProposal.organization_id == org,
            FinanceProposal.snapshot_sha256 == checksum,
            FinanceProposal.maker_identity == principal.identity,
        )
    )
    if row is None:
        row = FinanceProposal(
            organization_id=org,
            case_id=case_id,
            receipt_id=UUID(snapshot["inputs"]["receipt_id"]),
            policy_id=body.policy_id,
            source_review_id=body.source_review_id,
            maker_identity=principal.identity,
            maker=principal.provenance(),
            state="DRAFT",
            snapshot=snapshot,
            snapshot_sha256=checksum,
            journals=[j.model_dump(mode="json") for j in journals],
            treatments=[t.model_dump(mode="json") for t in treatments],
        )
        compare_locked(session, org, row, snapshot, settings)
        authorities(session, org, row, verifier)
        session.add(row)
        session.flush()
        history(session, org, row, principal, "CREATED")
        transition(row.state, "VALIDATED")
        row.state, row.version = "VALIDATED", row.version + 1
        history(session, org, row, principal, "DETERMINISTIC_VALIDATION")
        audit(session, org, principal, "finance.proposed", proposal_id=row.id)
    remember(session, org, key, stamp, "PROPOSE", {"id": str(row.id)}, principal)
    session.commit()
    return row


def request_approval(session, org, identifier, body, key, principal, settings, verifier):
    principal.require("PROPOSE", org)
    return change(
        session, org, identifier, body, key, principal, settings, verifier, "PENDING_APPROVAL"
    )


def change(session, org, identifier, body, key, principal, settings, verifier, target):
    principal.require("PROPOSE" if target == "PENDING_APPROVAL" else "APPROVE", org)
    stamp = fingerprint(target, identifier, body, principal)
    previous = replay(session, org, key, stamp)
    if previous:
        row = owned(session, FinanceProposal, org, identifier)
        session.commit()
        return row
    row = owned(session, FinanceProposal, org, identifier)
    case_id, snapshot_body = row.case_id, row.snapshot["body"]
    session.rollback()  # No locks held over the independent read-only preflight.
    try:
        preflight, _, _ = evaluate(
            session.get_bind(), org, case_id, ProposalInput.model_validate(snapshot_body), settings
        )
    except CaseError:
        invalidate(session, org, identifier, principal)
        raise CaseError("STALE_OR_UNVERIFIED_PROPOSAL") from None
    lock_company(session, org)
    if replay(session, org, key, stamp):
        row = owned(session, FinanceProposal, org, identifier)
        session.commit()
        return row
    row = owned(session, FinanceProposal, org, identifier)
    if row.version != body.expected_version or row.snapshot_sha256 != body.expected_snapshot_sha256:
        raise CaseError("STALE_FINANCE_VERSION")
    compare_locked(session, org, row, preflight, settings)
    spec = authorities(session, org, row, verifier)
    check_identity(verifier, row.maker, "PROPOSE", org)
    if target == "PENDING_APPROVAL":
        if str(principal.subject) != row.maker["subject"]:
            raise CaseError("ONLY_MAKER_CAN_SUBMIT", 403)
    else:
        principal.require("APPROVE", org)
        if str(principal.subject) == row.maker["subject"]:
            raise CaseError("MAKER_CHECKER_REQUIRED", 403)
    if target not in EDGES.get(row.state, set()):
        raise CaseError("INVALID_FINANCE_TRANSITION")
    transition(row.state, target)
    row.state, row.version = target, row.version + 1
    history(session, org, row, principal, getattr(body, "reason", "SUBMITTED"))
    if target == "APPROVED":
        session.add(
            FinanceApproval(
                organization_id=org,
                proposal_id=row.id,
                proposal_version=row.version,
                snapshot_sha256=row.snapshot_sha256,
                approver_identity=principal.identity,
                approver=principal.provenance(),
                expires_at=min(
                    principal.expires_at,
                    datetime.now(UTC) + timedelta(seconds=spec.approval_ttl_seconds),
                ),
            )
        )
    audit(session, org, principal, "finance." + target.lower(), proposal_id=row.id)
    remember(session, org, key, stamp, target, {"id": str(row.id)}, principal)
    session.commit()
    return row


def invalidate(session, org, identifier, principal):
    lock_company(session, org)
    row = owned(session, FinanceProposal, org, identifier)
    if "INVALIDATED" in EDGES.get(row.state, set()):
        row.state, row.version = "INVALIDATED", row.version + 1
        history(session, org, row, principal, "STALE_OR_UNVERIFIED_INPUTS")
        audit(session, org, principal, "finance.invalidated", proposal_id=row.id)
        session.commit()
