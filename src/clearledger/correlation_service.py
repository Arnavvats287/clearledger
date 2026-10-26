"""Transactional correlation review and existing case-merge orchestration."""

from uuid import UUID

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.case_events import publish
from clearledger.case_lifecycle import ensure_receipt_case, merge, revise
from clearledger.case_models import CaseDocument
from clearledger.case_repository import members, root, scoped
from clearledger.case_sources import current_context
from clearledger.correlation_contract import ALGORITHM, DecisionView, TaskView
from clearledger.correlation_models import CorrelationDecision, CorrelationTask
from clearledger.correlation_sources import context
from clearledger.document_contract import ExtractionError
from clearledger.matching import digest, lock_company, owned
from clearledger.models import BankTransaction, DocumentAssociation, DocumentExtraction, Receipt
from clearledger.review_service import current_reviewer

ACTIONS = {
    "READY_FOR_REVIEW": "CONFIRM_OR_REJECT_VERIFIED_ASSOCIATION",
    "MISSING_AUTHENTICATED_CORRELATION_EVIDENCE": "REGISTER_AUTHENTICATED_REMITTANCE_WITH_UTR",
    "CONFLICTING_SOURCE_EVIDENCE": "RESOLVE_CONFLICTING_SIGNED_SOURCES",
    "AMBIGUOUS_RECEIPTS": "OBTAIN_UNIQUE_BANK_SOURCE_REFERENCE",
    "SEARCH_INCOMPLETE": "REDUCE_SOURCE_CANDIDATES_AND_REVIEW",
    "SOURCE_PRECONDITIONS_NOT_MET": "RESOLVE_IDENTITY_OR_SOURCE_PRECONDITIONS",
}


def refresh(session, org, case, doc_id, settings, store, actor="correlation-worker"):
    extraction = session.scalar(
        select(DocumentExtraction)
        .where(DocumentExtraction.organization_id == org, DocumentExtraction.document_id == doc_id)
        .order_by(DocumentExtraction.extraction_version.desc())
        .limit(1)
    )
    if (
        extraction is None
        or extraction.error_code
        or extraction.status not in {"SUCCEEDED", "NEEDS_REVIEW"}
    ):
        return None
    snap = context(session, org, extraction, settings, store)
    stamp = digest(snap)
    prior = scoped(session, CorrelationTask, org, document_id=doc_id, input_sha256=stamp)
    if prior:
        return prior
    task = CorrelationTask(
        organization_id=org,
        case_id=case.id,
        document_id=doc_id,
        extraction_id=extraction.id,
        input_sha256=stamp,
        actor_id=actor,
        snapshot=snap,
    )
    session.add(task)
    session.flush()
    publish(
        session,
        org,
        "case.correlation_review_requested",
        "case_id",
        case.id,
        actor,
        {
            "task_id": str(task.id),
            "reason": snap["reason"],
            "next_action": ACTIONS[snap["reason"]],
            "financial_authority": False,
        },
        key={"correlation_task": str(task.id)},
        queued=False,
    )
    return task


def refresh_pending(session, org, settings, store, receipt_id):
    # Bounded source-change fanout, including document cases without a customer yet.
    receipt = owned(session, Receipt, org, receipt_id)
    bank = owned(session, BankTransaction, org, receipt.bank_transaction_id)
    ids = list(
        session.scalars(
            select(CorrelationTask.document_id)
            .where(
                CorrelationTask.organization_id == org,
                CorrelationTask.snapshot["signed_utr_references"].contains(
                    [bank.external_transaction_id]
                ),
            )
            .distinct()
            .limit(201)
        )
    )
    if len(ids) > 200:
        raise CaseError("CORRELATION_NOTIFICATION_LIMIT")
    for doc_id in ids:
        link = scoped(session, CaseDocument, org, document_id=doc_id)
        if link:
            refresh(session, org, root(session, org, link.case_id), doc_id, settings, store)


def task_view(session, org, task, settings, store):
    extraction = owned(session, DocumentExtraction, org, task.extraction_id)
    try:
        stale = digest(context(session, org, extraction, settings, store)) != task.input_sha256
    except (CaseError, ExtractionError):
        stale = True
    decision = scoped(session, CorrelationDecision, org, task_id=task.id)
    status = (
        ("CONFIRMED" if decision.decision == "CONFIRM" else "REJECTED") if decision else "PENDING"
    )
    return TaskView(
        id=task.id,
        case_id=root(session, org, task.case_id).id,
        document_id=task.document_id,
        extraction_id=task.extraction_id,
        input_sha256=task.input_sha256,
        reason=task.snapshot["reason"],
        next_action=(
            "REFRESH_CORRELATION_EVIDENCE"
            if stale
            else "VIEW_LINKED_CASE_AND_FINDINGS"
            if status == "CONFIRMED"
            else "OBTAIN_NEW_EVIDENCE_AFTER_REJECTION"
            if status == "REJECTED"
            else ACTIONS[task.snapshot["reason"]]
        ),
        candidates=task.snapshot["candidates"],
        status="STALE" if stale else status,
        is_stale=stale,
        created_at=task.created_at,
    )


def decision_view(row, session, org, settings, store):
    result = DecisionView.model_validate(row, from_attributes=True)
    task = owned(session, CorrelationTask, org, row.task_id)
    result.is_stale = task_view(session, org, task, settings, store).is_stale
    return result


def decide(session, org, task_id, body, key, reviewer, settings, verifier, store):
    reviewer.require("CONTROL")
    lock_company(session, org)
    session.info["review_verifier"] = verifier
    session.info["source_correlation_settings"] = settings
    current_reviewer(session, org, reviewer, "CONTROL")
    stamp = digest(
        {"task_id": str(task_id), "body": body.model_dump(mode="json"), "actor": reviewer.identity}
    )
    prior = scoped(session, CorrelationDecision, org, idempotency_key=key)
    if prior:
        if prior.request_sha256 != stamp:
            raise CaseError("CORRELATION_IDEMPOTENCY_CONFLICT")
        task = owned(session, CorrelationTask, org, prior.task_id)
        if task_view(session, org, task, settings, store).is_stale:
            raise CaseError("STALE_CORRELATION_EVIDENCE")
        return prior
    task = owned(session, CorrelationTask, org, task_id)
    if scoped(session, CorrelationDecision, org, task_id=task.id):
        raise CaseError("CORRELATION_TASK_ALREADY_DECIDED")
    if reviewer.identity == task.actor_id:
        raise CaseError("CORRELATION_INDEPENDENT_REVIEWER_REQUIRED", 403)
    case = root(session, org, task.case_id)
    if (
        case.version != body.expected_case_version
        or case.context_sha256 != body.expected_context_sha256
        or digest(current_context(session, org, case, store)) != case.context_sha256
    ):
        raise CaseError("STALE_CORRELATION_CASE")
    extraction = owned(session, DocumentExtraction, org, task.extraction_id)
    snap = context(session, org, extraction, settings, store)
    if body.expected_task_sha256 != task.input_sha256 or digest(snap) != task.input_sha256:
        raise CaseError("STALE_CORRELATION_EVIDENCE")
    association = None
    candidate = None
    if body.decision == "CONFIRM":
        if snap["reason"] != "READY_FOR_REVIEW":
            raise CaseError("AUTHORITATIVE_CORRELATION_REQUIRED")
        candidate = snap["candidates"][0]
        association = DocumentAssociation(
            organization_id=org,
            document_id=task.document_id,
            extraction_id=extraction.id,
            receipt_id=UUID(candidate["receipt_id"]),
            status="LINKED",
            input_sha256=task.input_sha256,
            inputs=snap,
            result={"algorithm": ALGORITHM, "task_id": str(task.id), "financial_authority": False},
        )
        session.add(association)
        session.flush()
    row = CorrelationDecision(
        organization_id=org,
        task_id=task.id,
        idempotency_key=key,
        request_sha256=stamp,
        decision=body.decision,
        actor={**reviewer.provenance, "review_role": reviewer.role},
        receipt_id=UUID(candidate["receipt_id"]) if candidate else None,
        invoice_id=UUID(candidate["invoice_id"]) if candidate else None,
        association_id=association.id if association else None,
    )
    session.add(row)
    session.flush()
    if association:
        receipt_case = ensure_receipt_case(
            session, org, owned(session, Receipt, org, row.receipt_id), reviewer.identity, store
        )
        if case.id != receipt_case.id:
            case = merge(session, org, case, receipt_case, reviewer.identity, store, association.id)
            if case.id != root(session, org, receipt_case.id).id:
                raise CaseError("CORRELATION_MERGE_CONFLICT")
        else:
            revise(session, org, case, reviewer.identity, "case.correlation_confirmed", store)
        if task.document_id not in {
            d.document_id
            for d in session.scalars(
                select(CaseDocument).where(
                    CaseDocument.organization_id == org,
                    CaseDocument.case_id.in_(members(session, org, case)),
                )
            )
        }:
            raise CaseError("CORRELATION_MERGE_CONFLICT")
    publish(
        session,
        org,
        "case.correlation_reviewed",
        "case_id",
        case.id,
        reviewer.identity,
        {
            "task_id": str(task.id),
            "decision_id": str(row.id),
            "decision": row.decision,
            "financial_authority": False,
        },
        key={"correlation_decision": str(row.id)},
        queued=False,
    )
    session.commit()
    return row
