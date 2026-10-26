"""Deterministic bounded independent-source correlation; no model or human labels as proof."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.case_sources import extraction_facts
from clearledger.correlation_contract import ALGORITHM
from clearledger.evidence_contract import RecordInput
from clearledger.evidence_domain import authenticated, validity
from clearledger.evidence_ingestion import configured_sources, validate_record
from clearledger.evidence_models import EvidenceRecord
from clearledger.evidence_repository import latest_clause
from clearledger.matching import bank_valid, build_snapshot, digest, owned
from clearledger.models import BankTransaction, DocumentExtraction, Invoice, Receipt

MAX_RECORDS = 50
MAX_PROOFS = 100
MAX_CANDIDATES = 50


def context(session, org, extraction, settings, store):
    doc, facts = extraction_facts(session, org, extraction, store)
    latest = session.scalar(
        select(DocumentExtraction.id)
        .where(DocumentExtraction.organization_id == org, DocumentExtraction.document_id == doc.id)
        .order_by(DocumentExtraction.extraction_version.desc())
        .limit(1)
    )
    records = list(
        session.scalars(
            select(EvidenceRecord)
            .where(
                EvidenceRecord.organization_id == org,
                EvidenceRecord.document_id == doc.id,
                EvidenceRecord.kind == "REMITTANCE",
                latest_clause(),
            )
            .order_by(EvidenceRecord.id)
            .limit(MAX_RECORDS + 1)
        )
    )
    sources = configured_sources(settings)
    observations, candidates = [], {}
    signed_references = set()
    invalid_signed_reference = False
    incomplete = len(records) > MAX_RECORDS
    work = 0
    for row in records[:MAX_RECORDS]:
        if work >= MAX_PROOFS:
            incomplete = True
            break
        body = RecordInput.model_validate(row.manifest)
        validate_record(session, org, body, store)
        trusted = row.content_sha256 == digest(body.model_dump(mode="json")) and authenticated(
            org, body, sources
        )
        observations.append(
            {
                "id": str(row.id),
                "sha256": row.content_sha256,
                "trusted": trusted,
                "customer_id": str(body.customer_id),
                "invoice_id": str(body.invoice_id),
            }
        )
        if not trusted:
            continue
        # UTR evidence comes from the signed immutable excerpt, never an LLM's value.
        matches = list(
            re.finditer(
                r"\bUTR\s*:\s*([A-Za-z0-9][A-Za-z0-9_./-]{0,99})\b",
                body.excerpt.quote,
                re.IGNORECASE,
            )
        )
        if len(matches) != 1:
            invalid_signed_reference = True
            continue
        match = matches[0]
        signed_references.add(match[1])
        invoice = owned(session, Invoice, org, body.invoice_id)
        rows = list(
            session.execute(
                select(Receipt, BankTransaction)
                .join(
                    BankTransaction,
                    (BankTransaction.id == Receipt.bank_transaction_id)
                    & (BankTransaction.organization_id == Receipt.organization_id),
                )
                .where(
                    Receipt.organization_id == org,
                    BankTransaction.organization_id == org,
                    BankTransaction.external_transaction_id == match[1],
                )
                .limit(101)
            )
        )
        if len(rows) > 100:
            incomplete = True
            continue
        for receipt, bank in rows:
            work += 1
            if work > MAX_PROOFS:
                incomplete = True
                break
            _, _, snap = build_snapshot(session, org, receipt.id)
            identity = snap["decision"]
            as_of = (
                invoice.issued_date
                if body.date_basis == "INVOICE_ISSUED"
                else bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
            )
            reasons = validity(body, trusted, True, as_of, datetime.now(UTC))
            if not bank_valid(session, org, bank):
                reasons.append("INVALID_BANK_SOURCE")
            if identity["identity"] != "RESOLVED" or identity["customers"] != [
                str(body.customer_id)
            ]:
                reasons.append("CUSTOMER_IDENTITY_CONFLICT_OR_MISSING")
            if (
                invoice.status != "OPEN"
                or invoice.open_amount_paise <= 0
                or receipt.unapplied_amount_paise <= 0
            ):
                reasons.append("INELIGIBLE_FINANCIAL_RECORD")
            if facts is None or extraction.id != latest or not facts.claims:
                reasons.append("STALE_OR_INVALID_EXTRACTION")
            elif {r.value for r in facts.invoice_references} != {invoice.invoice_number}:
                reasons.append("EXTRACTION_INVOICE_CONFLICT")
            elif facts.utr_references and {r.value for r in facts.utr_references} != {match[1]}:
                reasons.append("EXTRACTION_UTR_CONFLICT")
            key = (str(receipt.id), str(invoice.id), str(body.customer_id))
            if key not in candidates and len(candidates) >= MAX_CANDIDATES:
                incomplete = True
                break
            value = candidates.setdefault(
                key,
                {
                    "receipt_id": str(receipt.id),
                    "receipt_version": receipt.version,
                    "invoice_id": str(invoice.id),
                    "invoice_version": invoice.version,
                    "customer_id": str(body.customer_id),
                    "identity_sha256": digest(snap),
                    "evidence_ids": [],
                    "utr_span": {
                        "page": body.excerpt.page,
                        "start": body.excerpt.start + match.start(1),
                        "end": body.excerpt.start + match.end(1),
                        "quote": match[1],
                    },
                    "reasons": [],
                },
            )
            value["evidence_ids"].append(str(row.id))
            value["reasons"] = sorted(set(value["reasons"]) | set(reasons))
    values = sorted(candidates.values(), key=lambda v: (v["receipt_id"], v["invoice_id"]))
    for value in values:
        value["evidence_ids"].sort()
    owners = {(o["customer_id"], o["invoice_id"]) for o in observations if o["trusted"]}
    reason = (
        "SEARCH_INCOMPLETE"
        if incomplete
        else "CONFLICTING_SOURCE_EVIDENCE"
        if len(owners) > 1 or len(signed_references) > 1 or invalid_signed_reference
        else "AMBIGUOUS_RECEIPTS"
        if len(values) > 1
        else "MISSING_AUTHENTICATED_CORRELATION_EVIDENCE"
        if not values
        else "SOURCE_PRECONDITIONS_NOT_MET"
        if values[0]["reasons"]
        else "READY_FOR_REVIEW"
    )
    return {
        "algorithm": ALGORITHM,
        "document_id": str(doc.id),
        "document_version": doc.version,
        "raw_sha256": doc.content_sha256,
        "canonical_sha256": doc.canonical_sha256,
        "extraction_id": str(extraction.id),
        "latest_extraction_id": str(latest),
        "evidence": observations,
        "signed_utr_references": sorted(signed_references),
        "candidates": values,
        "reason": reason,
    }


def accepted_invoices(session, org, case_ids):
    from clearledger.correlation_models import CorrelationDecision, CorrelationTask

    result = set(
        session.scalars(
            select(CorrelationDecision.invoice_id)
            .join(
                CorrelationTask,
                (CorrelationTask.id == CorrelationDecision.task_id)
                & (CorrelationTask.organization_id == CorrelationDecision.organization_id),
            )
            .where(
                CorrelationDecision.organization_id == org,
                CorrelationTask.organization_id == org,
                CorrelationTask.case_id.in_(case_ids),
                CorrelationDecision.decision == "CONFIRM",
            )
            .distinct()
            .limit(2001)
        )
    )
    if len(result) > 2000:
        raise CaseError("CASE_ANALYSIS_LIMIT")
    return result
