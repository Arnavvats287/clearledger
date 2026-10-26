"""Validate existing source contracts without elevating source consistency to authority."""

from uuid import UUID

from sqlalchemy import func, select

from clearledger.advanced_matching import ALGORITHM
from clearledger.advanced_matching import context as advanced_context
from clearledger.case_domain import CaseError
from clearledger.case_models import CaseDocument, CaseInvoice, CaseReceipt, Claim, EvidenceLink
from clearledger.case_repository import group_rows, members
from clearledger.document_contract import (
    SCHEMA_VERSION,
    Extraction,
    ExtractionError,
    validate_semantics,
)
from clearledger.documents import association_context, integrity
from clearledger.matching import build_snapshot, digest, owned
from clearledger.models import Document, DocumentAssociation, DocumentExtraction, Invoice
from clearledger.remittance_parser import structured


def extraction_facts(session, org, extraction, store):
    doc = owned(session, Document, org, extraction.document_id)
    integrity(doc, store)
    if (
        extraction.status not in {"SUCCEEDED", "NEEDS_REVIEW"}
        or extraction.error_code
        or not extraction.result
    ):
        return doc, None
    if extraction.schema_version != SCHEMA_VERSION:
        raise ExtractionError("UNSUPPORTED_EXTRACTION_SCHEMA")
    facts = Extraction.model_validate(extraction.result)
    if doc.mime == "application/json":
        # Reparse actual structured fields; generic substring validation alone
        # cannot prove a JSON value occupies the claimed field.
        if structured(doc.pages[0]).model_dump() != facts.model_dump():
            raise ExtractionError("STRUCTURED_SOURCE_MISMATCH")
    else:
        validate_semantics(facts, doc.pages)
    return doc, facts


def proposal_current(session, org, proposal, settings):
    if proposal.snapshot.get("algorithm") == ALGORITHM:
        _, _, snapshot = advanced_context(
            session,
            org,
            proposal.receipt_id,
            settings.matching_limits,
            proposal.snapshot["use_structured_allocations"],
        )
    else:
        _, _, snapshot = build_snapshot(session, org, proposal.receipt_id)
    return digest(snapshot) == proposal.snapshot_sha256


def association_current(session, org, association, store):
    if association.inputs.get("algorithm") == "source-correlation-v1":
        from clearledger.correlation_sources import context

        settings = session.info.get("source_correlation_settings")
        if settings is None:
            return False
        extraction = owned(session, DocumentExtraction, org, association.extraction_id)
        return (
            digest(context(session, org, extraction, settings, store)) == association.input_sha256
        )
    doc = owned(session, Document, org, association.document_id)
    extraction = owned(session, DocumentExtraction, org, association.extraction_id)
    inputs, _, _, _ = association_context(
        session, org, doc, extraction, association.inputs["verified_utr_values"], store
    )
    return digest(inputs) == association.input_sha256


def current_context(session, org, case, store):
    ids = members(session, org, case)
    receipts = []
    for link in group_rows(session, CaseReceipt, org, ids, limit=100):
        _, _, snapshot = build_snapshot(session, org, link.receipt_id)
        from clearledger.finance_models import CashAllocation

        posted = list(
            session.scalars(
                select(CashAllocation)
                .where(
                    CashAllocation.organization_id == org,
                    CashAllocation.receipt_id == link.receipt_id,
                )
                .order_by(CashAllocation.id)
                .limit(1001)
            )
        )
        if len(posted) > 1000:
            raise CaseError("CASE_ANALYSIS_LIMIT")
        if posted:
            owners = {str(a.customer_id) for a in posted}
            if len(owners) != 1:
                raise CaseError("POSTED_RECEIPT_CUSTOMER_CONFLICT")
            snapshot["posted_customer_id"] = next(iter(owners))
            snapshot["posted_allocations"] = [
                {
                    "id": str(a.id),
                    "journal_id": str(a.journal_id),
                    "invoice_id": str(a.invoice_id),
                    "amount_paise": a.amount_paise,
                }
                for a in posted
            ]
        receipts.append(snapshot)
    docs = []
    for link in group_rows(session, CaseDocument, org, ids, limit=100):
        doc = owned(session, Document, org, link.document_id)
        try:
            integrity(doc, store)
            valid = True
        except ExtractionError:
            valid = False
        latest = session.scalar(
            select(func.max(DocumentExtraction.extraction_version)).where(
                DocumentExtraction.organization_id == org, DocumentExtraction.document_id == doc.id
            )
        )
        associations = list(
            session.scalars(
                select(DocumentAssociation)
                .where(
                    DocumentAssociation.organization_id == org,
                    DocumentAssociation.document_id == doc.id,
                )
                .order_by(DocumentAssociation.id)
                .limit(101)
            )
        )
        if len(associations) > 100:
            raise CaseError("CASE_ANALYSIS_LIMIT")
        association_inputs = []
        for association in associations:
            try:
                active = association_current(session, org, association, store)
            except ExtractionError:
                active = False
            association_inputs.append(
                {
                    "id": str(association.id),
                    "status": association.status,
                    "current": active,
                    "input_sha256": association.input_sha256,
                }
            )
        docs.append(
            {
                "id": str(doc.id),
                "version": doc.version,
                "raw": doc.content_sha256,
                "canonical": doc.canonical_sha256,
                "integrity": valid,
                "latest_extraction": latest,
                "associations": association_inputs,
            }
        )
    invoices = []
    from clearledger.correlation_sources import accepted_invoices

    for link in group_rows(session, CaseInvoice, org, ids):
        invoice = owned(session, Invoice, org, link.invoice_id)
        invoices.append(
            {
                "id": str(invoice.id),
                "customer": str(invoice.customer_id),
                "version": invoice.version,
                "open_paise": invoice.open_amount_paise,
                "status": invoice.status,
                "source": invoice.payload_sha256,
            }
        )
    # Preserve legacy context ordering/hashes when there are no new correlation links.
    existing_ids = {i["id"] for i in invoices}
    for invoice_id in sorted(accepted_invoices(session, org, ids)):
        if str(invoice_id) not in existing_ids:
            invoice = owned(session, Invoice, org, invoice_id)
            invoices.append(
                {
                    "id": str(invoice.id),
                    "customer": str(invoice.customer_id),
                    "version": invoice.version,
                    "open_paise": invoice.open_amount_paise,
                    "status": invoice.status,
                    "source": invoice.payload_sha256,
                }
            )
    context = {
        "receipts": receipts,
        "documents": docs,
        "invoices": invoices,
        "claims": [
            {"id": str(c.id), "version": c.version, "state": c.state, "assertion": c.fingerprint}
            for c in group_rows(session, Claim, org, ids)
        ],
        "evidence": [str(e.id) for e in group_rows(session, EvidenceLink, org, ids)],
    }
    from clearledger.evidence_repository import case_facts

    owners = {
        UUID(c)
        for r in receipts
        for c in r["decision"]["customers"]
        if r["decision"]["identity"] == "RESOLVED"
    }
    invoice_ids = {i["id"] for r in receipts for i in r["invoices"]}
    invoice_ids.update(i["id"] for i in invoices)
    facts = case_facts(session, org, owners, invoice_ids, store)
    if facts:
        context["external_evidence"] = facts
    return context


def claim_basis(session, org, case, claim, store, *, context=None):
    ids = members(session, org, case)
    evidence = [
        e for e in group_rows(session, EvidenceLink, org, ids) if e.claim_id in (None, claim.id)
    ]
    doc_ids = {claim.document_id, *[e.document_id for e in evidence]}
    context = current_context(session, org, case, store) if context is None else context
    basis = {
        "claim": str(claim.id),
        "version": claim.version,
        "state": claim.state,
        "receipts": context["receipts"],
        "invoices": context["invoices"],
        "documents": [d for d in context["documents"] if d["id"] in {str(i) for i in doc_ids}],
        "evidence": [str(e.id) for e in evidence],
    }
    latest = session.scalar(
        select(DocumentExtraction)
        .where(
            DocumentExtraction.organization_id == org,
            DocumentExtraction.document_id == claim.document_id,
        )
        .order_by(DocumentExtraction.extraction_version.desc())
        .limit(1)
    )
    references = (
        {r["value"] for r in latest.result.get("invoice_references", [])} if latest else set()
    )
    external = [
        e
        for e in context.get("external_evidence", [])
        if claim.category in e["categories"]
        and (e["invoice_number"] is None or not references or e["invoice_number"] in references)
    ]
    if external:
        basis["external_evidence"] = external
    return digest(basis)


def invoice_ids(proposal):
    result = set()
    if proposal.invoice_id:
        result.add(proposal.invoice_id)
    from uuid import UUID

    for candidate in proposal.result.get("candidates", []):
        if isinstance(candidate, dict):
            result.update(UUID(a["invoice_id"]) for a in candidate.get("allocations", []))
    return result
