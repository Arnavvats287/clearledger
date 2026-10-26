"""Fixed typed read-only evidence functions. Never model-supplied SQL or writes."""

from uuid import UUID

from sqlalchemy import func, select, text

from clearledger.case_domain import CaseError
from clearledger.case_models import CaseInvoice, Claim, ClaimSource
from clearledger.case_repository import group_rows, members, root
from clearledger.case_sources import current_context, extraction_facts
from clearledger.data_contract import InvoiceInput
from clearledger.document_contract import ExtractionError
from clearledger.document_privacy import project
from clearledger.evidence_contract import (
    Hit,
    NativePointer,
    RecordInput,
    SearchInput,
    SearchResult,
)
from clearledger.evidence_domain import authenticated
from clearledger.evidence_ingestion import configured_sources, record_view, validate_record
from clearledger.evidence_models import EvidenceRecord
from clearledger.evidence_repository import candidates, current
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.matching import digest, owned, source_rows, source_valid
from clearledger.models import (
    Customer,
    Document,
    DocumentExtraction,
    Invoice,
    SourceImport,
)

TOOLS = {
    "find_contract_clauses": "CONTRACT",
    "find_promotions": "PROMOTION",
    "get_wms_deliveries": "WMS",
    "get_proof_of_delivery": "POD",
    "get_tagged_tax_evidence": "TAX",
    "get_invoice_evidence": "INVOICE",
    "get_remittance_evidence": "REMITTANCE",
}


def begin_readonly(session, org):
    # Must be the first statement of a fresh transaction. READ ONLY is enforced
    # by PostgreSQL, not a promise attached to an arbitrary SQL tool.
    session.execute(text("SET TRANSACTION READ ONLY"))
    session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
    session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
    session.info["evidence_readonly"] = True
    import hashlib

    key = int.from_bytes(hashlib.sha256(org.bytes).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": key})


def masked(text_value):
    try:
        return project([text_value]).pages[0]
    except ExtractionError:
        return "[PRIVACY_REVIEW_REQUIRED]"


class EvidenceReader:
    def __init__(self, session, org, settings):
        session.info["source_correlation_settings"] = settings
        if (
            not session.info.get("evidence_readonly")
            or session.scalar(text("SHOW transaction_read_only")) != "on"
        ):
            raise CaseError("READ_ONLY_EVIDENCE_TRANSACTION_REQUIRED", 500)
        self.session, self.org, self.settings = session, org, settings
        self.store = EvidenceOriginals(settings.document_root)
        self.sources = configured_sources(settings)

    def scope(self, case_id, body):
        session, org = self.session, self.org
        case = root(session, org, case_id)
        context = current_context(session, org, case, self.store)
        if (
            case.version != body.expected_case_version
            or case.context_sha256 != body.expected_context_sha256
            or digest(context) != case.context_sha256
        ):
            raise CaseError("STALE_EVIDENCE_CASE_CONTEXT")
        if case.customer_id is None or case.customer_id != body.customer_id:
            raise CaseError("VERIFIED_CASE_CUSTOMER_REQUIRED", 404)
        ids = members(session, org, case)
        invoice_ids = {r.invoice_id for r in group_rows(session, CaseInvoice, org, ids)}
        invoice_ids.update(UUID(i["id"]) for r in context["receipts"] for i in r["invoices"])
        if len(invoice_ids) > 1000:
            raise CaseError("EVIDENCE_INVOICE_SCOPE_BUDGET")
        self.invoice_ids = invoice_ids
        if body.invoice_id:
            invoice = owned(session, Invoice, org, body.invoice_id)
            if invoice.id not in invoice_ids or invoice.customer_id != case.customer_id:
                raise CaseError("INVOICE_OUTSIDE_EVIDENCE_CASE", 404)
        if body.claim_id:
            claim = owned(session, Claim, org, body.claim_id)
            if claim.case_id not in ids:
                raise CaseError("CLAIM_OUTSIDE_EVIDENCE_CASE", 404)
        return case, ids

    def document_hit(self, row):
        body = RecordInput.model_validate(row.manifest)
        valid = row.content_sha256 == digest(body.model_dump(mode="json"))
        try:
            validate_record(self.session, self.org, body, self.store)
        except (ExtractionError, CaseError):
            valid = False
        span = body.excerpt
        visible = masked(span.quote) if valid else "[SOURCE_INTEGRITY_FAILURE]"
        facts = {}
        if visible != "[PRIVACY_REVIEW_REQUIRED]" and valid:
            fact = body.fact
            if fact.type == "CONTRACT":
                facts["limit_paise"] = fact.limit.value
            elif fact.type in {"WMS", "POD"}:
                facts.update(
                    shipped_quantity=fact.shipped.value,
                    delivered_quantity=fact.delivered.value,
                    damaged_quantity=fact.damaged.value,
                    unit_value_paise=fact.unit_value.value,
                    unit=fact.unit,
                )
            else:
                facts["amount_paise"] = fact.amount.value
                if fact.type == "TAX":
                    facts["tax_tag"] = fact.tax_tag
        return Hit(
            record_type="DOCUMENT_EVIDENCE",
            id=row.id,
            version=row.revision,
            kind=row.kind,
            document_id=body.document_id,
            document_version=body.document_version,
            raw_sha256=body.raw_sha256,
            canonical_sha256=body.canonical_sha256,
            page=span.page,
            start=span.start,
            end=span.end,
            excerpt=visible,
            source_authenticated=valid and authenticated(self.org, body, self.sources),
            source_integrity=valid,
            is_current=current(self.session, self.org, row),
            metadata={
                "effective_from": str(body.effective_from),
                "effective_to": str(body.effective_to),
                "categories": body.categories,
                "signed": body.signed_at is not None,
                "approved": body.approved_at is not None,
                "invoice_id": str(body.invoice_id) if body.invoice_id else None,
                "facts": facts,
                "privacy_review_required": visible == "[PRIVACY_REVIEW_REQUIRED]",
            },
        )

    def invoice_hit(self, invoice):
        customer = owned(self.session, Customer, self.org, invoice.customer_id)
        original = InvoiceInput(
            customer_reference=customer.external_reference,
            invoice_number=invoice.invoice_number,
            issued_date=invoice.issued_date.isoformat(),
            due_date=invoice.due_date.isoformat(),
            original_amount_paise=invoice.original_amount_paise,
            open_amount_paise=invoice.initial_open_amount_paise,
            currency=invoice.currency,
        )
        valid = source_valid(self.session, self.org, invoice, "invoices", original)
        source = owned(self.session, SourceImport, self.org, invoice.source_import_id)
        visible = masked(
            f"INVOICE: {invoice.invoice_number}; {invoice.original_amount_paise} paise"
        )
        return Hit(
            record_type="INVOICE",
            id=invoice.id,
            version=invoice.version,
            kind="INVOICE",
            document_id=None,
            document_version=None,
            raw_sha256=source.content_sha256,
            canonical_sha256=invoice.payload_sha256,
            page=None,
            start=None,
            end=None,
            excerpt=visible,
            source_authenticated=False,
            source_integrity=valid,
            is_current=True,
            metadata={
                "source_import_id": str(source.id),
                "source_row": invoice.source_row,
                "original_amount_paise": invoice.original_amount_paise
                if visible != "[PRIVACY_REVIEW_REQUIRED]"
                else None,
                "open_amount_paise": invoice.open_amount_paise
                if visible != "[PRIVACY_REVIEW_REQUIRED]"
                else None,
                "privacy_review_required": visible == "[PRIVACY_REVIEW_REQUIRED]",
            },
        )

    def remittance_hits(self, ids, invoice_id=None):
        output = []
        invoice = owned(self.session, Invoice, self.org, invoice_id) if invoice_id else None
        for claim in group_rows(self.session, Claim, self.org, ids, limit=200):
            doc = owned(self.session, Document, self.org, claim.document_id)
            sources = list(
                self.session.scalars(
                    select(ClaimSource)
                    .where(
                        ClaimSource.organization_id == self.org, ClaimSource.claim_id == claim.id
                    )
                    .limit(101)
                )
            )
            if len(sources) > 100:
                raise CaseError("EVIDENCE_SOURCE_BUDGET")
            valid = False
            active = False
            relevant = invoice is None
            latest = self.session.scalar(
                select(func.max(DocumentExtraction.extraction_version)).where(
                    DocumentExtraction.organization_id == self.org,
                    DocumentExtraction.document_id == doc.id,
                )
            )
            provenance = []
            current_references = set()
            uncertainty = "unknown"
            for source in sources:
                run = owned(self.session, DocumentExtraction, self.org, source.extraction_id)
                try:
                    _, facts = extraction_facts(self.session, self.org, run, self.store)
                    if facts and any(
                        c.model_dump(mode="json") == claim.assertion for c in facts.claims
                    ):
                        valid = True
                        active |= run.extraction_version == latest
                        if run.extraction_version == latest:
                            current_references = {r.value for r in facts.invoice_references}
                            uncertainty = facts.uncertainty
                        provenance.append(str(run.id))
                        relevant |= invoice is not None and any(
                            r.value == invoice.invoice_number for r in facts.invoice_references
                        )
                except ExtractionError:
                    pass
            span = claim.assertion["description"]
            if not relevant:
                continue
            visible = masked(span["quote"]) if valid else "[SOURCE_INTEGRITY_FAILURE]"
            output.append(
                Hit(
                    record_type="REMITTANCE",
                    id=claim.id,
                    version=claim.version,
                    kind="REMITTANCE",
                    document_id=doc.id,
                    document_version=doc.version,
                    raw_sha256=doc.content_sha256,
                    canonical_sha256=doc.canonical_sha256,
                    page=span["page"],
                    start=span["start"],
                    end=span["end"],
                    excerpt=visible,
                    source_authenticated=False,
                    source_integrity=valid,
                    is_current=valid
                    and active
                    and (invoice is None or invoice.invoice_number in current_references),
                    metadata={
                        "amount_paise": claim.amount_paise
                        if visible != "[PRIVACY_REVIEW_REQUIRED]"
                        else None,
                        "privacy_review_required": visible == "[PRIVACY_REVIEW_REQUIRED]",
                        "category": claim.category,
                        "extraction_ids": provenance,
                        "invoice_reference_count": len(current_references),
                        "extraction_uncertainty": uncertainty,
                    },
                )
            )
        return output

    def search(self, case_id, body):
        case, ids = self.scope(case_id, body)
        kind = TOOLS[body.tool]
        rows = candidates(
            self.session,
            self.org,
            case.customer_id,
            [kind],
            body.invoice_id,
            body.query,
            body.after_id,
            body.limit,
            invoice_ids=self.invoice_ids,
        )
        more = len(rows) > body.limit
        hits = [self.document_hit(r) for r in rows[: body.limit]]
        if kind == "INVOICE":
            invoices = list(
                self.session.scalars(
                    select(Invoice)
                    .where(
                        Invoice.organization_id == self.org,
                        Invoice.customer_id == case.customer_id,
                        Invoice.id.in_(self.invoice_ids),
                        *(
                            [
                                func.to_tsvector(
                                    "simple",
                                    func.concat(
                                        Invoice.invoice_number, " ", Invoice.original_amount_paise
                                    ),
                                ).op("@@")(func.plainto_tsquery("simple", body.query))
                            ]
                            if body.query
                            else []
                        ),
                        *([Invoice.id == body.invoice_id] if body.invoice_id else []),
                        *([Invoice.id > body.after_id] if body.after_id else []),
                    )
                    .order_by(Invoice.id)
                    .limit(body.limit + 1)
                )
            )
            hits += [
                self.invoice_hit(i)
                for i in invoices
                if body.after_id is None or i.id > body.after_id
            ]
        elif kind == "REMITTANCE":
            hits += [
                h
                for h in self.remittance_hits(ids, body.invoice_id)
                if body.after_id is None or h.id > body.after_id
                if not body.query or body.query.casefold() in h.excerpt.casefold()
            ]
        hits.sort(key=lambda h: h.id)
        more |= len(hits) > body.limit
        return SearchResult(
            items=hits[: body.limit],
            has_more=more,
            next_after_id=hits[body.limit - 1].id if more else None,
            search_complete=not more,
            reasons=["MORE_RESULTS"] if more else [],
            input_sha256=digest(
                {
                    "body": body.model_dump(mode="json"),
                    "case": case.context_sha256,
                    "hits": [h.model_dump(mode="json") for h in hits[: body.limit]],
                }
            ),
        )

    def pointer(self, case_id, record_id, body):
        case, _ = self.scope(case_id, body)
        row = owned(self.session, EvidenceRecord, self.org, record_id)
        if row.customer_id != case.customer_id or (
            row.invoice_id
            and (
                row.invoice_id not in self.invoice_ids
                or (body.invoice_id is not None and row.invoice_id != body.invoice_id)
            )
        ):
            raise CaseError("EVIDENCE_POINTER_OUTSIDE_SCOPE", 404)
        validate_record(
            self.session, self.org, RecordInput.model_validate(row.manifest), self.store
        )
        if row.content_sha256 != digest(row.manifest):
            raise CaseError("EVIDENCE_MANIFEST_HASH_MISMATCH")
        return record_view(self.session, self.org, row, self.settings)

    def native_pointer(self, case_id, record_id, kind, body, expected_version, expected_hash):
        _, ids = self.scope(case_id, body)
        if kind == "INVOICE":
            if record_id not in self.invoice_ids:
                raise CaseError("INVOICE_OUTSIDE_EVIDENCE_CASE", 404)
            invoice = owned(self.session, Invoice, self.org, record_id)
            hit = self.invoice_hit(invoice)
            if not hit.source_integrity:
                raise CaseError("INVOICE_SOURCE_INTEGRITY_FAILURE")
            if (invoice.version, hit.raw_sha256) != (expected_version, expected_hash):
                raise CaseError("STALE_NATIVE_EVIDENCE_POINTER")
            source = owned(self.session, SourceImport, self.org, invoice.source_import_id)
            original = next(
                row
                for number, row in source_rows(self.session, source, "invoices")
                if number == invoice.source_row
            )
            return NativePointer(
                record_type="INVOICE",
                id=invoice.id,
                version=invoice.version,
                raw_sha256=source.content_sha256,
                source_import_id=source.id,
                source_row=invoice.source_row,
                payload=original.model_dump(mode="json"),
                source_current=True,
            )
        claim = owned(self.session, Claim, self.org, record_id)
        hit = next(
            (h for h in self.remittance_hits(ids, body.invoice_id) if h.id == claim.id), None
        )
        if hit is None or not hit.source_integrity:
            raise CaseError("REMITTANCE_OUTSIDE_SCOPE_OR_INVALID", 404)
        if (claim.version, hit.raw_sha256) != (expected_version, expected_hash):
            raise CaseError("STALE_NATIVE_EVIDENCE_POINTER")
        return NativePointer(
            record_type="REMITTANCE",
            id=claim.id,
            version=claim.version,
            raw_sha256=hit.raw_sha256,
            document_id=hit.document_id,
            document_version=hit.document_version,
            span=claim.assertion["description"],
            payload=claim.assertion,
            source_current=hit.is_current,
        )

    def verify(self, case_id, body):
        from clearledger.evidence_verification import verify_evidence

        return verify_evidence(self, case_id, body)


def find_contract_clauses(
    reader: EvidenceReader, case_id: UUID, request: SearchInput
) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "find_contract_clauses"}))


def find_promotions(reader: EvidenceReader, case_id: UUID, request: SearchInput) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "find_promotions"}))


def get_wms_deliveries(reader: EvidenceReader, case_id: UUID, request: SearchInput) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "get_wms_deliveries"}))


def get_proof_of_delivery(
    reader: EvidenceReader, case_id: UUID, request: SearchInput
) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "get_proof_of_delivery"}))


def get_tagged_tax_evidence(
    reader: EvidenceReader, case_id: UUID, request: SearchInput
) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "get_tagged_tax_evidence"}))


def get_invoice_evidence(
    reader: EvidenceReader, case_id: UUID, request: SearchInput
) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "get_invoice_evidence"}))


def get_remittance_evidence(
    reader: EvidenceReader, case_id: UUID, request: SearchInput
) -> SearchResult:
    return reader.search(case_id, request.model_copy(update={"tool": "get_remittance_evidence"}))
