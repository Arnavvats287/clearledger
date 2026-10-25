"""Serialized versioned review commands, immutable correspondence, no send capability."""

from uuid import UUID

from sqlalchemy import text

from clearledger.case_domain import CASE_EDGES, CaseError, CaseState
from clearledger.case_lifecycle import record, revise
from clearledger.case_models import Case, Claim
from clearledger.case_repository import members, scoped
from clearledger.case_service import attach
from clearledger.case_sources import current_context
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.finance_models import FinanceProposal
from clearledger.finance_repository import check_identity
from clearledger.matching import digest, lock_company, owned
from clearledger.review_contract import ActionView
from clearledger.review_lifecycle import closure_facts
from clearledger.review_models import (
    DemoRevocation,
    DemoSession,
    DemoUser,
    ReviewAction,
    ReviewAudit,
    ReviewCommand,
)
from clearledger.review_sources import draft_sources


def current_reviewer(session, org, reviewer, operation):
    from datetime import UTC, datetime

    if reviewer.trusted:
        current = check_identity(
            session.info.get("review_verifier"), reviewer.trusted.provenance(), "REVIEW_READ", org
        )
        permission = {
            "CONTROLLER": "REVIEW_CONTROL",
            "AR_ANALYST": "REVIEW_WORK",
            "AUDITOR": "REVIEW_READ",
        }[reviewer.role]
        current.require(permission, org)
        if operation == "CLOSE":
            current.require("APPROVE", org)
    else:
        user = owned(session, DemoUser, org, reviewer.subject)
        proof = reviewer.provenance
        login = owned(session, DemoSession, org, UUID(proof["session_id"]))
        if (
            not user.enabled
            or user.version != proof["user_version"]
            or user.role != reviewer.role
            or login.user_id != user.id
            or login.user_version != user.version
            or login.expires_at <= datetime.now(UTC)
            or scoped(session, DemoRevocation, org, session_id=login.id)
        ):
            raise CaseError("DEMO_AUTHORITY_REVOKED", 403)


def action_view(session, org, action, settings):
    case = owned(session, Case, org, action.case_id)
    stale = case.version != action.result_case_version
    if not stale:
        stale = (
            digest(current_context(session, org, case, EvidenceOriginals(settings.document_root)))
            != case.context_sha256
        )
    return ActionView(
        id=action.id,
        case_id=action.case_id,
        kind=action.kind,
        basis_case_version=action.basis_case_version,
        result_case_version=action.result_case_version,
        actor=action.actor,
        content=action.content,
        source_sha256=action.source_sha256,
        created_at=action.created_at,
        is_stale=stale,
    )


def command(session, org, case_id, operation, body, key, reviewer, settings, verifier):
    reviewer.require(
        "CLOSE"
        if operation == "CLOSE"
        else "CONTROL"
        if operation == "REQUEST_EVIDENCE"
        else "WORK"
    )
    stamp = digest(
        {
            "case": str(case_id),
            "operation": operation,
            "body": body.model_dump(mode="json"),
            "actor": reviewer.identity,
        }
    )
    # Draft preflight uses the existing genuinely READ ONLY evidence reader and
    # never holds the command's exclusive company lock across a second connection.
    session.rollback()
    sources = (
        draft_sources(session.get_bind(), org, case_id, body, settings)
        if operation == "DRAFT"
        else None
    )
    session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
    session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
    lock_company(session, org)
    session.info["review_verifier"] = verifier
    current_reviewer(session, org, reviewer, operation)
    case = owned(session, Case, org, case_id)
    if case.merged_into_id:
        raise CaseError("CASE_MERGED_USE_CANONICAL_ID")
    store = EvidenceOriginals(settings.document_root)
    current_hash = digest(current_context(session, org, case, store))
    prior = scoped(session, ReviewCommand, org, idempotency_key=key)
    if prior:
        if prior.request_sha256 != stamp:
            raise CaseError("REVIEW_IDEMPOTENCY_CONFLICT")
        action = owned(session, ReviewAction, org, prior.action_id)
        if case.version != action.result_case_version or current_hash != case.context_sha256:
            raise CaseError("STALE_REVIEW_REPLAY")
        return action
    if (
        case.version != body.expected_case_version
        or current_hash != case.context_sha256
        or case.context_sha256 != body.expected_context_sha256
    ):
        raise CaseError("STALE_REVIEW_INPUTS")
    content = {
        "reason": body.reason,
        "comment": body.comment,
        "comment_trust": "UNTRUSTED",
        "transmitted": False,
    }
    reply_id = getattr(body, "in_reply_to", None)
    proposal_id = getattr(body, "proposal_id", None)
    if operation == "DRAFT":
        content.update(
            sources=sources,
            template="evidence-request-v1",
            recipient=None,
            subject="Draft evidence request",
            text="Please provide supporting records for the listed invoice and claim IDs. "
            "Amounts are recorded facts, not accepted deductions. No message was sent.",
        )
    elif operation == "REQUEST_EVIDENCE":
        if proposal_id:
            proposal = owned(session, FinanceProposal, org, proposal_id)
            if (
                proposal.case_id not in members(session, org, case)
                or proposal.version != body.expected_proposal_version
                or proposal.snapshot_sha256 != body.expected_snapshot_sha256
                or proposal.state not in {"VALIDATED", "PENDING_APPROVAL", "APPROVED"}
            ):
                raise CaseError("STALE_REVIEW_PROPOSAL")
            if str(reviewer.subject) == proposal.maker["subject"]:
                raise CaseError("MAKER_CHECKER_REQUIRED", 403)
        claims = [owned(session, Claim, org, i) for i in body.claim_ids]
        if any(c.case_id not in members(session, org, case) for c in claims):
            raise CaseError("CLAIM_CASE_MISMATCH", 404)
        if case.state in {"NEW", "MATCHING", "CLOSED"}:
            raise CaseError("CASE_NOT_READY_FOR_EVIDENCE_REQUEST")
        revise(
            session,
            org,
            case,
            reviewer.identity,
            "review.evidence_requested",
            store,
            affected={c.id for c in claims},
            details={"reason": body.reason},
        )
        if case.state == "INVESTIGATING":
            case.state, case.version = "AWAITING_EVIDENCE", case.version + 1
            record(session, org, case, reviewer.identity, "review.awaiting_evidence", store)
        content["claim_ids"] = [str(c.id) for c in claims]
    elif operation == "RESPONSE":
        if reply_id:
            parent = owned(session, ReviewAction, org, reply_id)
            if parent.case_id not in members(session, org, case) or parent.kind not in {
                "DRAFT",
                "REQUEST_EVIDENCE",
            }:
                raise CaseError("INVALID_RESPONSE_THREAD", 422)
            if parent.kind == "REQUEST_EVIDENCE" and set(parent.content["claim_ids"]) != {
                str(i) for i in body.evidence.claim_ids
            }:
                raise CaseError("RESPONSE_REQUEST_TARGET_MISMATCH", 422)
        for identifier, version in body.expected_claim_versions.items():
            claim = owned(session, Claim, org, identifier)
            if claim.case_id not in members(session, org, case) or claim.version != version:
                raise CaseError("STALE_RESPONSE_CLAIM")
        attach(session, org, case, body.evidence, reviewer.identity, store)
        revise(
            session,
            org,
            case,
            reviewer.identity,
            "review.customer_response_recorded",
            store,
            affected=set(body.expected_claim_versions) if body.expected_claim_versions else None,
            details={"document_id": str(body.evidence.document_id), "reason": body.reason},
        )
        content.update(
            evidence=body.evidence.model_dump(mode="json"),
            sender_authenticated=False,
            assertion_trust="UNVERIFIED_CUSTOMER_RESPONSE",
        )
    elif operation == "CLOSE":
        if body.reason != "SETTLED_AND_COMPLETE":
            raise CaseError("CLOSURE_REASON_REQUIRED", 422)
        content["closure_proof"] = closure_facts(session, org, case, store, reviewer)
        if case.state == "AWAITING_EVIDENCE":
            case.state, case.version = "INVESTIGATING", case.version + 1
            record(
                session,
                org,
                case,
                reviewer.identity,
                "review.closure_reassessment_verified",
                store,
                {"reason": body.reason},
            )
        if case.state in {"INVESTIGATING", "AWAITING_REVIEW"}:
            # Operational readiness is justified by the already posted, zero-open
            # financial proof above, never by a new settlement or an actor label.
            case.state, case.version = "READY_TO_APPLY", case.version + 1
            record(
                session,
                org,
                case,
                reviewer.identity,
                "review.closure_readiness_verified",
                store,
                {"reason": body.reason},
            )
        case.state, case.version = "CLOSED", case.version + 1
        record(
            session,
            org,
            case,
            reviewer.identity,
            "review.case_closed",
            store,
            {"reason": body.reason},
        )
    elif operation == "REOPEN":
        if (
            body.reason != "NEW_INFORMATION"
            or CaseState.INVESTIGATING not in CASE_EDGES[CaseState(case.state)]
        ):
            raise CaseError("INVALID_REVIEW_REOPEN")
        revise(
            session,
            org,
            case,
            reviewer.identity,
            "review.case_reopened",
            store,
            details={"reason": body.reason},
        )
    elif operation != "COMMENT":
        raise CaseError("REVIEW_OPERATION_NOT_ALLOWED", 422)
    action = ReviewAction(
        organization_id=org,
        case_id=case.id,
        kind=operation,
        basis_case_version=body.expected_case_version,
        result_case_version=case.version,
        actor=reviewer.provenance,
        content=content,
        source_sha256=digest(
            sources or {"context": current_hash, "body": body.model_dump(mode="json")}
        ),
        in_reply_to=reply_id,
        proposal_id=proposal_id,
    )
    session.add(action)
    session.flush()
    session.add(
        ReviewAudit(
            organization_id=org,
            actor=reviewer.provenance,
            operation=operation,
            outcome="COMPLETED",
            code=body.reason,
            target_id=case_id,
        )
    )
    session.add(
        ReviewCommand(
            organization_id=org, idempotency_key=key, request_sha256=stamp, action_id=action.id
        )
    )
    session.commit()
    return action
