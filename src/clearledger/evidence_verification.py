"""Deterministic read-only verification orchestration, separate from retrieval/ingestion."""

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from clearledger.case_domain import CaseError
from clearledger.case_models import CaseReceipt, Claim
from clearledger.case_repository import group_rows
from clearledger.document_contract import ExtractionError
from clearledger.evidence_contract import Citation, Finding, RecordInput, Verification, VerifyInput
from clearledger.evidence_domain import EXPECTED_KIND, aggregate, authenticated, predicate, validity
from clearledger.evidence_ingestion import validate_record
from clearledger.evidence_models import EvidenceRecord
from clearledger.evidence_reader import EvidenceReader
from clearledger.evidence_repository import BUDGET, candidates, current
from clearledger.matching import digest, owned
from clearledger.models import BankTransaction, Invoice, Receipt


def verify_evidence(reader: EvidenceReader, case_id: UUID, body: VerifyInput) -> Verification:
    case, ids = reader.scope(case_id, body)
    claim = owned(reader.session, Claim, reader.org, body.claim_id)
    invoice = owned(reader.session, Invoice, reader.org, body.invoice_id)
    if not reader.invoice_hit(invoice).source_integrity:
        raise CaseError("INVOICE_SOURCE_INTEGRITY_FAILURE")
    applicable = {
        "DELIVERY_SHORTAGE": {"short_shipment"},
        "DELIVERY_DAMAGE": {"damage"},
        "PROMOTION_AMOUNT": {"rebate", "early_discount"},
        "TAX_DOCUMENT": {"tax"},
    }
    if body.question in applicable and claim.category not in applicable[body.question]:
        return Verification(
            outcome="NOT_APPLICABLE",
            reasons=["QUESTION_CLAIM_MISMATCH"],
            findings=[],
            input_sha256=digest(body.model_dump(mode="json")),
            search_complete=True,
        )
    # Independently inspect the source claim and current extraction, not its label.
    source_hits = reader.remittance_hits(ids, invoice.id)
    if not any(h.id == claim.id and h.source_integrity and h.is_current for h in source_hits):
        raise CaseError("CLAIM_SOURCE_INTEGRITY_FAILURE")
    if any(h.id == claim.id and h.metadata["invoice_reference_count"] != 1 for h in source_hits):
        return Verification(
            outcome="INSUFFICIENT",
            reasons=["CLAIM_INVOICE_RELATIONSHIP_AMBIGUOUS"],
            findings=[],
            input_sha256=digest(body.model_dump(mode="json")),
            search_complete=True,
        )
    if any(
        h.id == claim.id and h.metadata["extraction_uncertainty"] != "none" for h in source_hits
    ):
        return Verification(
            outcome="INSUFFICIENT",
            reasons=["CLAIM_EXTRACTION_UNCERTAIN"],
            findings=[],
            input_sha256=digest(body.model_dump(mode="json")),
            search_complete=True,
        )
    rows = candidates(
        reader.session, reader.org, case.customer_id, EXPECTED_KIND[body.question], invoice.id
    )
    complete = len(rows) <= BUDGET
    selected = {r.id: r for r in rows[:BUDGET]}
    findings = []
    if claim.amount_paise is not None and claim.amount_paise > invoice.original_amount_paise:
        findings.append(
            Finding(outcome="INSUFFICIENT", reasons=["CLAIM_EXCEEDS_INVOICE_BASIS"], record_ids=[])
        )
    for citation in body.citations:
        row = owned(reader.session, EvidenceRecord, reader.org, citation.record_id)
        if row.customer_id != case.customer_id or row.invoice_id not in (None, invoice.id):
            raise CaseError("EVIDENCE_POINTER_OUTSIDE_SCOPE", 404)
        manifest = RecordInput.model_validate(row.manifest)
        expected = Citation(
            record_id=row.id,
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            raw_sha256=manifest.raw_sha256,
            canonical_sha256=manifest.canonical_sha256,
            span=manifest.excerpt,
        )
        if citation != expected:
            findings.append(
                Finding(
                    outcome="INSUFFICIENT",
                    reasons=["FORGED_OR_STALE_CITATION"],
                    record_ids=[row.id],
                )
            )
        selected[row.id] = row
    deliveries = []
    for row in selected.values():
        record = RecordInput.model_validate(row.manifest)
        try:
            validate_record(reader.session, reader.org, record, reader.store)
            if row.content_sha256 != digest(record.model_dump(mode="json")):
                raise ExtractionError("EVIDENCE_MANIFEST_HASH_MISMATCH")
        except (CaseError, ExtractionError):
            findings.append(
                Finding(
                    outcome="INSUFFICIENT",
                    reasons=["SOURCE_INTEGRITY_FAILURE"],
                    record_ids=[row.id],
                )
            )
            continue
        if claim.category not in record.categories:
            findings.append(
                Finding(
                    outcome="NOT_APPLICABLE",
                    reasons=["CLAIM_CATEGORY_MISMATCH"],
                    record_ids=[row.id],
                )
            )
            continue
        as_of = invoice.issued_date
        if (
            claim.category == "early_discount"
            and body.question == "PROMOTION_AMOUNT"
            and record.date_basis != "RECEIPT_OCCURRED"
        ):
            findings.append(
                Finding(
                    outcome="INSUFFICIENT",
                    reasons=["RECEIPT_DATE_BASIS_REQUIRED"],
                    record_ids=[row.id],
                )
            )
            continue
        if record.date_basis == "RECEIPT_OCCURRED":
            receipts = group_rows(reader.session, CaseReceipt, reader.org, ids, limit=100)
            target = body.receipt_id or (receipts[0].receipt_id if len(receipts) == 1 else None)
            if target not in {r.receipt_id for r in receipts}:
                findings.append(
                    Finding(
                        outcome="INSUFFICIENT",
                        reasons=["RECEIPT_DATE_AMBIGUOUS"],
                        record_ids=[row.id],
                    )
                )
                continue
            receipt = owned(reader.session, Receipt, reader.org, target)
            bank = owned(reader.session, BankTransaction, reader.org, receipt.bank_transaction_id)
            as_of = bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        reasons = validity(
            record,
            authenticated(reader.org, record, reader.sources),
            current(reader.session, reader.org, row),
            as_of,
            datetime.now(UTC),
        )
        if reasons:
            outcome = (
                "NOT_APPLICABLE" if reasons == ["OUTSIDE_EFFECTIVE_PERIOD"] else "INSUFFICIENT"
            )
            findings.append(Finding(outcome=outcome, reasons=reasons, record_ids=[row.id]))
            continue
        if record.fact.type in {"WMS", "POD"}:
            deliveries.append((row.id, record.fact))
            if (
                record.fact.shipped.value * record.fact.unit_value.value
                > invoice.original_amount_paise
            ):
                findings.append(
                    Finding(
                        outcome="INSUFFICIENT",
                        reasons=["DELIVERY_EXCEEDS_INVOICE_BASIS"],
                        record_ids=[row.id],
                    )
                )
                continue
        target_amount = (
            invoice.original_amount_paise
            if body.question == "INVOICE_AMOUNT"
            else claim.amount_paise
        )
        findings.append(predicate(body.question, target_amount, record.fact, row.id))
    if body.question in {"DELIVERY_SHORTAGE", "DELIVERY_DAMAGE"}:
        pod = [f for _, f in deliveries if f.type == "POD"]
        if not pod:
            findings.append(
                Finding(outcome="INSUFFICIENT", reasons=["MISSING_SIGNED_POD"], record_ids=[])
            )
        if len({f.shipment.value for _, f in deliveries}) > 1:
            findings.append(
                Finding(outcome="INSUFFICIENT", reasons=["MULTIPLE_DELIVERY_GROUPS"], record_ids=[])
            )
        facts = {
            (f.shipped.value, f.delivered.value, f.damaged.value, f.unit_value.value)
            for _, f in deliveries
        }
        if len(facts) > 1:
            findings.append(
                Finding(
                    outcome="INSUFFICIENT",
                    reasons=["CONFLICTING_DELIVERY_RECORDS"],
                    record_ids=[],
                )
            )
    outcome, reasons = aggregate(findings, complete)
    if claim.category == "tax":
        outcome, reasons = "INSUFFICIENT", sorted(set(reasons) | {"NEEDS_TAX_REVIEW"})
    return Verification(
        outcome=outcome,
        reasons=reasons,
        findings=findings,
        search_complete=complete,
        input_sha256=digest(
            {
                "request": body.model_dump(mode="json"),
                "case": case.context_sha256,
                "records": sorted((str(r.id), r.content_sha256) for r in selected.values()),
                "findings": [f.model_dump(mode="json") for f in findings],
            }
        ),
    )
