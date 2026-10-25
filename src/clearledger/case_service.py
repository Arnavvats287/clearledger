"""Versioned nonfinancial commands and views. Transactions owned here or by worker."""

from sqlalchemy import func, select

from clearledger.case_domain import (
    CaseError,
    CaseState,
    ClaimState,
    case_transition,
    claim_transition,
    claimed_total,
)
from clearledger.case_events import (
    document_changed,
    matching_evidence_registered,
    matching_proposed,
    receipt_accepted,
)
from clearledger.case_lifecycle import revise, settled_claims
from clearledger.case_models import (
    Case,
    CaseCommand,
    CaseDocument,
    CaseInvoice,
    CaseReceipt,
    Claim,
    ClaimSource,
    EvidenceLink,
)
from clearledger.case_processing import proposal_event
from clearledger.case_repository import group_rows, members, root, scoped
from clearledger.case_schemas import CaseView, ClaimView
from clearledger.case_sources import current_context, proposal_current
from clearledger.document_contract import (
    ExtractionError,
    Reference,
    empty_extraction,
    span_text,
    validate_semantics,
)
from clearledger.documents import integrity
from clearledger.matching import digest, lock_company, owned
from clearledger.models import (
    Document,
    DocumentEvent,
    DocumentExtraction,
    Invoice,
    MatchingEvidence,
    MatchingProposal,
    Receipt,
)
from clearledger.remittance_parser import structured


def view(session, org, case, store, requested=None):
    case = root(session, org, case.id)
    ids = members(session, org, case)
    current = digest(current_context(session, org, case, store))
    total, unknown = claimed_total([c.amount_paise for c in group_rows(session, Claim, org, ids)])
    return CaseView(
        id=case.id,
        requested_case_id=requested or case.id,
        organization_id=org,
        version=case.version,
        state=case.state,
        customer_id=case.customer_id,
        created_at=case.created_at,
        context_sha256=case.context_sha256,
        current_context_sha256=current,
        is_stale=current != case.context_sha256,
        attention_codes=case.attention_codes,
        receipt_ids=[r.receipt_id for r in group_rows(session, CaseReceipt, org, ids)],
        document_ids=[r.document_id for r in group_rows(session, CaseDocument, org, ids)],
        invoice_ids=sorted({r.invoice_id for r in group_rows(session, CaseInvoice, org, ids)}),
        claimed_total_paise=total,
        unknown_amount_count=unknown,
        verified_settled_paise=settled_claims(
            session, org, {c.id for c in group_rows(session, Claim, org, ids)}
        ),
    )


def claim_view(session, org, claim, store):
    latest = session.scalar(
        select(func.max(DocumentExtraction.extraction_version)).where(
            DocumentExtraction.organization_id == org,
            DocumentExtraction.document_id == claim.document_id,
        )
    )
    current = (
        session.scalar(
            select(ClaimSource.id)
            .join(
                DocumentExtraction,
                (ClaimSource.extraction_id == DocumentExtraction.id)
                & (ClaimSource.organization_id == DocumentExtraction.organization_id),
            )
            .where(
                ClaimSource.organization_id == org,
                ClaimSource.claim_id == claim.id,
                DocumentExtraction.extraction_version == latest,
                DocumentExtraction.error_code.is_(None),
            )
        )
        is not None
    )
    try:
        integrity(owned(session, Document, org, claim.document_id), store)
    except ExtractionError:
        current = False
    return ClaimView(
        id=claim.id,
        case_id=claim.case_id,
        canonical_case_id=root(session, org, claim.case_id).id,
        version=claim.version,
        state=claim.state,
        category=claim.category,
        amount_paise=claim.amount_paise,
        document_id=claim.document_id,
        assertion=claim.assertion,
        source_current=current,
    )


def attach(session, org, case, body, actor, store):
    doc = owned(session, Document, org, body.document_id)
    integrity(doc, store)
    if (doc.version, doc.content_sha256, doc.canonical_sha256) != (
        body.document_version,
        body.raw_sha256,
        body.canonical_sha256,
    ):
        raise CaseError("STALE_DOCUMENT_EVIDENCE")
    span_text(doc.pages, body.span)
    ids = members(session, org, case)
    claims = [owned(session, Claim, org, identifier) for identifier in set(body.claim_ids)]
    if any(c.case_id not in ids for c in claims):
        raise CaseError("CLAIM_CASE_MISMATCH", 422)
    existing_doc = scoped(session, CaseDocument, org, document_id=doc.id)
    already = existing_doc is not None and root(session, org, existing_doc.case_id).id == case.id
    if not already:
        if existing_doc is not None:
            raise CaseError("DOCUMENT_BELONGS_TO_ANOTHER_CASE", 422)
        if body.invoice_id is None or body.invoice_reference_span is None:
            raise CaseError("SOURCE_BACKED_INVOICE_ASSOCIATION_REQUIRED", 422)
        invoice = owned(session, Invoice, org, body.invoice_id)
        if (
            case.customer_id is None
            or invoice.customer_id != case.customer_id
            or not any(
                row.invoice_id == invoice.id for row in group_rows(session, CaseInvoice, org, ids)
            )
        ):
            raise CaseError("INVOICE_CASE_OWNER_MISMATCH", 422)
        extracted = empty_extraction()
        extracted.invoice_references = [
            Reference(value=invoice.invoice_number, span=body.invoice_reference_span)
        ]
        if doc.mime == "application/json":
            if extracted.invoice_references[0] not in structured(doc.pages[0]).invoice_references:
                raise CaseError("SOURCE_BACKED_INVOICE_ASSOCIATION_REQUIRED", 422)
        else:
            validate_semantics(extracted, doc.pages)
        session.add(CaseDocument(organization_id=org, case_id=case.id, document_id=doc.id))
    targets = claims or [None]
    affected = {c.id for c in claims} if claims else None
    inserted = False
    for claim in targets:
        physical = claim.case_id if claim else case.id
        key = digest(
            {
                "doc": str(doc.id),
                "claim": str(claim.id) if claim else None,
                "span": body.span.model_dump(),
                "relation": body.relation,
            }
        )
        if scoped(session, EvidenceLink, org, case_id=physical, evidence_key=key) is None:
            session.add(
                EvidenceLink(
                    organization_id=org,
                    case_id=physical,
                    claim_id=claim.id if claim else None,
                    document_id=doc.id,
                    document_version=doc.version,
                    raw_sha256=doc.content_sha256,
                    canonical_sha256=doc.canonical_sha256,
                    span=body.span.model_dump(),
                    relation=body.relation,
                    evidence_key=key,
                    actor_id=actor,
                )
            )
            inserted = True
    if inserted:
        revise(
            session,
            org,
            case,
            actor,
            "case.evidence_attached",
            store,
            affected=affected,
            details={"document_id": str(doc.id), "claim_ids": sorted(str(c.id) for c in claims)},
        )


def command(session, org, case_id, key, actor, operation, body, settings, store, claim_id=None):
    lock_company(session, org)
    case = owned(session, Case, org, case_id)
    if case.merged_into_id:
        raise CaseError("CASE_MERGED_USE_CANONICAL_ID")
    fingerprint = digest(
        {
            "operation": operation,
            "case_id": str(case_id),
            "claim_id": str(claim_id),
            "actor": actor,
            "body": body.model_dump(mode="json"),
        }
    )
    prior = scoped(session, CaseCommand, org, idempotency_key=key)
    if prior and (prior.case_id != case.id or prior.request_sha256 != fingerprint):
        raise CaseError("IDEMPOTENCY_CONFLICT")
    if (
        operation != "refresh"
        and digest(current_context(session, org, case, store)) != case.context_sha256
    ):
        raise CaseError("STALE_CASE_INPUTS_REFRESH_REQUIRED")
    if prior:
        if prior.result_case_version != case.version:
            raise CaseError("STALE_IDEMPOTENT_CASE_COMMAND")
        return prior.response
    if body.expected_case_version != case.version:
        raise CaseError("STALE_CASE_VERSION")
    if operation == "attach":
        attach(session, org, case, body, actor, store)
    elif operation == "transition":
        case_transition(CaseState(case.state), body.target)
        case.state = body.target
        revise(
            session,
            org,
            case,
            actor,
            "case.state_changed",
            store,
            invalidate=False,
            enqueue=body.target == CaseState.INVESTIGATING,
        )
    elif operation == "claim_transition":
        claim = owned(session, Claim, org, claim_id)
        if claim.case_id not in members(session, org, case):
            raise CaseError("CLAIM_CASE_MISMATCH", 422)
        if body.expected_claim_version != claim.version:
            raise CaseError("STALE_CLAIM_VERSION")
        claim_transition(ClaimState(claim.state), body.target, claim.category)
        claim.state = body.target
        claim.version += 1
        revise(
            session,
            org,
            case,
            actor,
            "claim.state_changed",
            store,
            affected={claim.id},
            changed_claims=[claim],
            reopen_claims=False,
            details={"claim_id": str(claim.id), "target": body.target},
        )
    elif operation in {"refresh", "investigate"}:
        revise(session, org, case, actor, "case." + operation + "_requested", store)
    elif operation == "bind":
        proposal = owned(session, MatchingProposal, org, body.matching_proposal_id)
        if proposal.receipt_id not in {
            r.receipt_id for r in group_rows(session, CaseReceipt, org, members(session, org, case))
        }:
            raise CaseError("PROPOSAL_RECEIPT_CASE_MISMATCH", 422)
        if not proposal_current(session, org, proposal, settings):
            raise CaseError("STALE_MATCHING_PROPOSAL")
        proposal_event(session, org, proposal, actor, settings, store)
    else:
        raise CaseError("CASE_OPERATION_NOT_ALLOWED", 422)
    response = view(session, org, case, store).model_dump(mode="json")
    session.add(
        CaseCommand(
            organization_id=org,
            case_id=case.id,
            idempotency_key=key,
            request_sha256=fingerprint,
            result_case_version=case.version,
            response=response,
        )
    )
    session.commit()
    return response


def reconcile(session, org, actor, body):
    lock_company(session, org)
    model = {
        "receipts": Receipt,
        "document_events": DocumentEvent,
        "matching_proposals": MatchingProposal,
        "matching_evidence": MatchingEvidence,
    }[body.source]
    statement = select(model).where(model.organization_id == org)
    if body.after_id is not None:
        statement = statement.where(model.id > body.after_id)
    rows = list(session.scalars(statement.order_by(model.id).limit(body.limit + 1)))
    from clearledger.case_models import DomainEvent

    before = session.scalar(
        select(func.count()).select_from(DomainEvent).where(DomainEvent.organization_id == org)
    )
    for row in rows[: body.limit]:
        if model is Receipt:
            receipt_accepted(session, row, actor)
        elif model is DocumentEvent:
            document_changed(session, row)
        elif model is MatchingEvidence:
            matching_evidence_registered(session, row, actor)
        else:
            matching_proposed(session, row, actor)
    session.flush()
    after = session.scalar(
        select(func.count()).select_from(DomainEvent).where(DomainEvent.organization_id == org)
    )
    session.commit()
    return {
        "published": after - before,
        "next_after_id": rows[body.limit - 1].id if len(rows) > body.limit else None,
        "has_more": len(rows) > body.limit,
    }
