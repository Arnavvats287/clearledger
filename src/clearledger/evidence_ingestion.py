"""Trusted application ingestion, separate from the database-read-only tool surface."""

from datetime import UTC, datetime

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.case_events import publish
from clearledger.case_lifecycle import revise
from clearledger.case_models import Case, CaseVersion
from clearledger.case_repository import root
from clearledger.document_runtime import LocalOriginals
from clearledger.documents import integrity
from clearledger.evidence_contract import Citation, RecordInput, RecordView
from clearledger.evidence_domain import authenticated, source_spans, trust_sources
from clearledger.evidence_models import EvidenceEvent, EvidenceRecord, EvidenceRequest
from clearledger.evidence_repository import current
from clearledger.matching import digest, lock_company, owned
from clearledger.models import Customer, Document, Invoice


def configured_sources(settings):
    raw = settings.evidence_trusted_sources_json
    sources = trust_sources(raw.get_secret_value() if raw else None)
    tokens = [
        s.get_secret_value() for s in (settings.document_api_token, settings.case_read_token) if s
    ]
    if any(source.secret in tokens for source in sources):
        raise CaseError("EVIDENCE_SIGNING_KEY_MUST_BE_SEPARATE", 503)
    return sources


def validate_record(session, org, body, store):
    doc = owned(session, Document, org, body.document_id)
    integrity(doc, store)
    if (doc.version, doc.content_sha256, doc.canonical_sha256, doc.parse_status) != (
        body.document_version,
        body.raw_sha256,
        body.canonical_sha256,
        "READY",
    ):
        raise CaseError("STALE_OR_UNPARSED_EVIDENCE_DOCUMENT")
    customer = owned(session, Customer, org, body.customer_id)
    invoice = owned(session, Invoice, org, body.invoice_id) if body.invoice_id else None
    if invoice and invoice.customer_id != customer.id:
        raise CaseError("EVIDENCE_INVOICE_OWNER_MISMATCH", 422)
    source_spans(
        body, doc.pages, customer.external_reference, invoice.invoice_number if invoice else None
    )
    return doc


def record_view(session, org, row, settings):
    body = RecordInput.model_validate(row.manifest)
    return RecordView(
        id=row.id,
        revision=row.revision,
        kind=row.kind,
        content_sha256=row.content_sha256,
        is_current=current(session, org, row),
        source_authenticated=authenticated(org, body, configured_sources(settings)),
        manifest=body,
        citation=Citation(
            record_id=row.id,
            document_id=body.document_id,
            document_version=body.document_version,
            raw_sha256=body.raw_sha256,
            canonical_sha256=body.canonical_sha256,
            span=body.excerpt,
        ),
    )


def register(session, org, body, actor, key, settings):
    lock_company(session, org)
    fingerprint = digest(body.model_dump(mode="json"))
    prior = session.scalar(
        select(EvidenceRequest).where(
            EvidenceRequest.organization_id == org, EvidenceRequest.idempotency_key == key
        )
    )
    if prior:
        if prior.request_sha256 != fingerprint or prior.actor_id != actor:
            raise CaseError("EVIDENCE_IDEMPOTENCY_CONFLICT")
        row = owned(session, EvidenceRecord, org, prior.record_id)
        validate_record(session, org, body, LocalOriginals(settings.document_root))
        return record_view(session, org, row, settings)
    validate_record(session, org, body, LocalOriginals(settings.document_root))
    if body.recorded_at > datetime.now(UTC):
        raise CaseError("EVIDENCE_SOURCE_FROM_FUTURE", 422)
    sources = configured_sources(settings)
    if body.signature and not authenticated(org, body, sources):
        raise CaseError("EVIDENCE_SOURCE_SIGNATURE_INVALID", 422)
    identity = (
        EvidenceRecord.organization_id == org,
        EvidenceRecord.source_system == body.source_system,
        EvidenceRecord.source_record_id == body.source_record_id,
    )
    row = session.scalar(
        select(EvidenceRecord).where(*identity, EvidenceRecord.revision == body.revision)
    )
    inserted = row is None
    if row:
        if row.content_sha256 != fingerprint:
            raise CaseError("EVIDENCE_REVISION_CONFLICT")
    else:
        latest = session.scalar(
            select(EvidenceRecord)
            .where(*identity)
            .order_by(EvidenceRecord.revision.desc())
            .limit(1)
        )
        if latest:
            if (body.revision, body.previous_id) != (latest.revision + 1, latest.id):
                raise CaseError("EVIDENCE_STALE_OR_NONCONTIGUOUS_REVISION")
            if (body.customer_id, body.invoice_id, body.fact.type) != (
                latest.customer_id,
                latest.invoice_id,
                latest.kind,
            ):
                raise CaseError("EVIDENCE_REVISION_IDENTITY_CHANGE", 422)
        elif body.revision != 1 or body.previous_id is not None:
            raise CaseError("EVIDENCE_FIRST_REVISION_REQUIRED")
        row = EvidenceRecord(
            organization_id=org,
            source_system=body.source_system,
            source_record_id=body.source_record_id,
            revision=body.revision,
            previous_id=body.previous_id,
            kind=body.fact.type,
            customer_id=body.customer_id,
            invoice_id=body.invoice_id,
            document_id=body.document_id,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            recorded_at=body.recorded_at,
            content_sha256=fingerprint,
            manifest=body.model_dump(mode="json"),
            excerpt=body.excerpt.quote,
        )
        session.add(row)
        session.flush()
    operation = EvidenceRequest(
        organization_id=org,
        record_id=row.id,
        idempotency_key=key,
        request_sha256=fingerprint,
        actor_id=actor,
    )
    session.add(operation)
    session.flush()
    session.add(
        EvidenceEvent(
            organization_id=org,
            record_id=row.id,
            request_id=operation.id,
            actor_id=actor,
            event_type="evidence.registered" if inserted else "evidence.replayed",
        )
    )
    if inserted:
        correlation_notified = set()
        if settings.case_auto_correlate_extractions and row.kind == "REMITTANCE":
            from clearledger.case_models import CaseDocument

            for link in session.scalars(
                select(CaseDocument).where(
                    CaseDocument.organization_id == org, CaseDocument.document_id == row.document_id
                )
            ):
                case = root(session, org, link.case_id)
                correlation_notified.add(case.id)
                publish(
                    session,
                    org,
                    "case.correlation_source_changed",
                    "case_id",
                    case.id,
                    actor,
                    {"record_id": str(row.id)},
                    key={"correlation_source": str(row.id), "case": str(case.id)},
                )
        # A company-scoped bounded source notification. Case processing owns
        # version/invalidation effects; registration never settles or changes claims.
        cases = list(
            session.scalars(
                select(Case)
                .where(
                    Case.organization_id == org,
                    Case.customer_id == body.customer_id,
                    Case.merged_into_id.is_(None),
                )
                .order_by(Case.id)
                .limit(201)
            )
        )
        if len(cases) > 200:
            raise CaseError("EVIDENCE_CASE_NOTIFICATION_LIMIT")
        for case in cases:
            if case.id in correlation_notified:
                continue  # One source notification/effect, not two for the same record/case.
            if body.invoice_id is not None:
                snapshot = session.scalar(
                    select(CaseVersion).where(
                        CaseVersion.organization_id == org,
                        CaseVersion.case_id == case.id,
                        CaseVersion.case_version == case.version,
                    )
                )
                context = snapshot.snapshot["context"]
                invoices = {i["id"] for r in context["receipts"] for i in r["invoices"]}
                invoices.update(i["id"] for i in context["invoices"])
                if str(body.invoice_id) not in invoices:
                    continue
            publish(
                session,
                org,
                "case.external_evidence_added",
                "case_id",
                case.id,
                actor,
                {"record_id": str(row.id)},
                case_version=case.version,
                key={"evidence": str(row.id), "case": str(case.id)},
            )
    session.commit()
    return record_view(session, org, row, settings)


def evidence_changed(session, org, event, settings, store):
    from uuid import UUID

    from clearledger.case_models import Claim
    from clearledger.case_repository import group_rows, members
    from clearledger.evidence_runtime import EvidenceOriginals

    store = EvidenceOriginals(settings.document_root)

    record = owned(session, EvidenceRecord, org, UUID(event.payload["record_id"]))
    case = root(session, org, event.case_id)
    if case.customer_id != record.customer_id:
        raise CaseError("EVIDENCE_CASE_OWNER_CHANGED")
    body = RecordInput.model_validate(record.manifest)
    # Source integrity is checked again at consumption, without invoking an LLM.
    validate_record(session, org, body, store)
    from clearledger.case_models import ClaimSource
    from clearledger.case_sources import extraction_facts
    from clearledger.models import DocumentExtraction

    invoice = owned(session, Invoice, org, body.invoice_id) if body.invoice_id else None
    affected = set()
    for claim in group_rows(session, Claim, org, members(session, org, case)):
        if claim.category not in body.categories:
            continue
        if invoice is None:
            affected.add(claim.id)
            continue
        sources = list(
            session.scalars(
                select(ClaimSource)
                .where(ClaimSource.organization_id == org, ClaimSource.claim_id == claim.id)
                .limit(101)
            )
        )
        if len(sources) > 100:
            raise CaseError("CASE_ANALYSIS_LIMIT")
        for source in sources:
            run = owned(session, DocumentExtraction, org, source.extraction_id)
            _, facts = extraction_facts(session, org, run, store)
            if facts and any(r.value == invoice.invoice_number for r in facts.invoice_references):
                affected.add(claim.id)
                break
    revise(
        session,
        org,
        case,
        event.actor_id,
        "case.external_evidence_observed",
        store,
        affected=affected,
        details={"record_id": str(record.id)},
    )
    return case
