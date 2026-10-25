"""Allowlisted event consumer and deterministic re-evaluation (no adjudicator/LLM)."""

from uuid import UUID

from sqlalchemy import select

from clearledger.case_domain import CaseState, case_transition
from clearledger.case_lifecycle import (
    ensure_document_case,
    ensure_receipt_case,
    merge,
    revise,
)
from clearledger.case_models import (
    CaseDocument,
    CaseInvalidation,
    CaseInvoice,
    CaseProposal,
    Claim,
    ClaimSource,
    DomainEvent,
    Hypothesis,
    Reevaluation,
)
from clearledger.case_repository import group_rows, members, root, scoped
from clearledger.case_schemas import ReevaluationPayload
from clearledger.case_sources import (
    association_current,
    claim_basis,
    current_context,
    extraction_facts,
    invoice_ids,
    proposal_current,
)
from clearledger.matching import digest, owned
from clearledger.models import (
    Document,
    DocumentAssociation,
    DocumentEvent,
    DocumentExtraction,
    MatchingEvidence,
    MatchingProposal,
    Receipt,
)


def parsed_claims(session, org, extraction, actor, store):
    doc, facts = extraction_facts(session, org, extraction, store)
    link = scoped(session, CaseDocument, org, document_id=doc.id)
    if facts is None and link is None:
        return None
    if (
        facts is not None
        and not (facts.claims or facts.invoice_references or facts.utr_references)
        and link is None
    ):
        return None
    case = ensure_document_case(session, org, doc, actor, store)
    changed = []
    affected = set()
    for index, assertion in enumerate(facts.claims if facts else []):
        value = assertion.model_dump(mode="json")
        fingerprint = digest(value)
        claim = scoped(session, Claim, org, document_id=doc.id, fingerprint=fingerprint)
        if claim is None:
            same_span = list(
                session.scalars(
                    select(Claim).where(Claim.organization_id == org, Claim.document_id == doc.id)
                )
            )
            if any(c.assertion["description"] == value["description"] for c in same_span):
                case.attention_codes = sorted(
                    set(case.attention_codes) | {"CONFLICTING_CLAIM_ASSERTIONS"}
                )
            claim = Claim(
                organization_id=org,
                case_id=case.id,
                document_id=doc.id,
                fingerprint=fingerprint,
                category=assertion.category,
                amount_paise=assertion.amount_paise,
                assertion=value,
            )
            session.add(claim)
            session.flush()
            changed.append(claim)
        if (
            scoped(session, ClaimSource, org, extraction_id=extraction.id, claim_index=index)
            is None
        ):
            session.add(
                ClaimSource(
                    organization_id=org,
                    claim_id=claim.id,
                    extraction_id=extraction.id,
                    claim_index=index,
                )
            )
        affected.add(claim.id)
    affected.update(
        c.id
        for c in group_rows(session, Claim, org, members(session, org, case))
        if c.document_id == doc.id
    )
    revise(
        session,
        org,
        case,
        actor,
        "case.remittance_observed",
        store,
        details={"document_id": str(doc.id), "extraction_id": str(extraction.id)},
        affected=affected,
        changed_claims=changed,
    )
    return case


def proposal_event(session, org, proposal, actor, settings, store):
    receipt = owned(session, Receipt, org, proposal.receipt_id)
    case = ensure_receipt_case(session, org, receipt, actor, store)
    current = proposal_current(session, org, proposal, settings)
    if current:
        for identifier in invoice_ids(proposal):
            if (
                scoped(
                    session,
                    CaseInvoice,
                    org,
                    case_id=case.id,
                    invoice_id=identifier,
                    matching_proposal_id=proposal.id,
                )
                is None
            ):
                session.add(
                    CaseInvoice(
                        organization_id=org,
                        case_id=case.id,
                        invoice_id=identifier,
                        matching_proposal_id=proposal.id,
                    )
                )
    revise(
        session,
        org,
        case,
        actor,
        "case.matching_observed",
        store,
        details={"matching_proposal_id": str(proposal.id), "source_current": current},
    )
    binding = CaseProposal(
        organization_id=org,
        case_id=case.id,
        matching_proposal_id=proposal.id,
        basis_case_version=case.version,
    )
    session.add(binding)
    return case


def document_event(session, org, event, settings, store):
    doc = owned(session, Document, org, event.document_id)
    if event.event_type == "document.extracted":
        extraction = owned(session, DocumentExtraction, org, event.entity_id)
        if extraction.document_id != doc.id:
            raise ValueError("Source extraction mismatch")
        return parsed_claims(session, org, extraction, event.actor_id, store)
    if event.event_type == "document.correlated":
        association = owned(session, DocumentAssociation, org, event.entity_id)
        if association.document_id != doc.id:
            raise ValueError("Source association mismatch")
        if association.status == "LINKED" and association_current(session, org, association, store):
            document_case = ensure_document_case(session, org, doc, event.actor_id, store)
            receipt = owned(session, Receipt, org, association.receipt_id)
            receipt_case = ensure_receipt_case(session, org, receipt, event.actor_id, store)
            if document_case.id == receipt_case.id:
                revise(
                    session,
                    org,
                    receipt_case,
                    event.actor_id,
                    "case.association_observed",
                    store,
                    details={"association_id": str(association.id)},
                )
                return receipt_case
            return merge(
                session, org, document_case, receipt_case, event.actor_id, store, association.id
            )
    link = scoped(session, CaseDocument, org, document_id=doc.id)
    if link:
        case = root(session, org, link.case_id)
        revise(
            session,
            org,
            case,
            event.actor_id,
            "case.document_observed",
            store,
            details={"document_event_id": str(event.id)},
        )
        return case
    return None


def reevaluate(session, org, event, store, settings=None):
    case = root(session, org, event.case_id)
    from clearledger.case_models import CaseVersion
    from clearledger.evidence_runtime import EvidenceOriginals

    revision = scoped(session, CaseVersion, org, case_id=case.id, case_version=case.version)
    if revision.snapshot["context"].get("external_evidence"):
        store = EvidenceOriginals(store.root)
    started_version = case.version
    ids = members(session, org, case)
    claims = group_rows(session, Claim, org, ids)
    payload = ReevaluationPayload.model_validate(event.payload)
    targets = set(payload.affected_claim_ids)
    cause = owned(session, DomainEvent, org, payload.cause_event_id)
    if cause.case_id not in ids or not targets.issubset({c.id for c in claims}):
        raise ValueError("Reevaluation source scope mismatch")
    while case.state in {"NEW", "MATCHING"}:
        target = CaseState.MATCHING if case.state == "NEW" else CaseState.INVESTIGATING
        case_transition(CaseState(case.state), target)
        case.state = target
        revise(
            session,
            org,
            case,
            "case-worker",
            "case.state_changed",
            store,
            invalidate=False,
            enqueue=False,
        )
    context = current_context(session, org, case, store)
    for claim in claims:
        if claim.id not in targets:
            continue
        basis = claim_basis(session, org, case, claim, store, context=context)
        invalid = select(CaseInvalidation.hypothesis_id).where(
            CaseInvalidation.organization_id == org, CaseInvalidation.hypothesis_id.is_not(None)
        )
        valid = session.scalar(
            select(Hypothesis).where(
                Hypothesis.organization_id == org,
                Hypothesis.claim_id == claim.id,
                Hypothesis.basis_sha256 == basis,
                Hypothesis.id.not_in(invalid),
            )
        )
        if valid is None:
            session.add(
                Hypothesis(
                    organization_id=org,
                    case_id=claim.case_id,
                    claim_id=claim.id,
                    basis_case_id=case.id,
                    basis_case_version=case.version,
                    basis_sha256=basis,
                    content={
                        "algorithm": "case-placeholder-v1",
                        "finding": "UNASSESSED",
                        "requires_human_review": True,
                        "financial_authority": False,
                    },
                )
            )
    if case.state == "INVESTIGATING":
        target = CaseState.AWAITING_REVIEW if case.attention_codes else CaseState.AWAITING_EVIDENCE
        case_transition(CaseState(case.state), target)
        case.state = target
        revise(
            session,
            org,
            case,
            "case-worker",
            "case.state_changed",
            store,
            invalidate=False,
            enqueue=False,
        )
    session.add(
        Reevaluation(
            organization_id=org,
            case_id=case.id,
            event_id=event.id,
            scheduled_version=event.case_version,
            evaluated_version=case.version,
            result={
                "affected_claim_ids": sorted(str(c.id) for c in claims if c.id in targets),
                "superseded_request": event.case_version != started_version,
                "finding": "REVIEW_REQUIRED",
                "financial_authority": False,
            },
        )
    )
    if settings is not None:
        from clearledger.investigation_service import schedule_affected

        schedule_affected(session, org, case, targets, settings, event.id)
    return case


def consume(session, org, event, settings, store):
    if event.event_type == "case.external_evidence_added":
        from clearledger.evidence_ingestion import evidence_changed

        return evidence_changed(session, org, event, settings, store)
    if event.event_type == "matching.evidence_registered":
        evidence = owned(
            session, MatchingEvidence, org, UUID(event.payload["matching_evidence_id"])
        )
        if evidence.receipt_id != event.receipt_id:
            raise ValueError("Source receipt mismatch")
        case = ensure_receipt_case(
            session, org, owned(session, Receipt, org, event.receipt_id), event.actor_id, store
        )
        revise(
            session,
            org,
            case,
            event.actor_id,
            "case.identity_evidence_observed",
            store,
            details={"matching_evidence_id": str(evidence.id)},
        )
        return case
    if event.event_type == "receipt.accepted":
        return ensure_receipt_case(
            session, org, owned(session, Receipt, org, event.receipt_id), event.actor_id, store
        )
    if event.event_type == "document.changed":
        return document_event(
            session,
            org,
            owned(session, DocumentEvent, org, event.document_event_id),
            settings,
            store,
        )
    if event.event_type == "matching.proposed":
        return proposal_event(
            session,
            org,
            owned(session, MatchingProposal, org, event.matching_proposal_id),
            event.actor_id,
            settings,
            store,
        )
    if event.event_type == "case.reevaluation.requested":
        return reevaluate(session, org, event, store, settings)
    raise ValueError("Event type not allowed")
