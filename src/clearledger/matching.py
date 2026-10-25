"""Verified local evidence and immutable proposals; no cash/AR mutation endpoints."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, text

from clearledger.data_contract import AliasInput, BankInput, timestamp
from clearledger.imports import ImportFailure, canonical, event, parse_csv
from clearledger.matching_domain import InvoiceState, decide, invoice_reference_span
from clearledger.models import (
    BankTransaction,
    Customer,
    Invoice,
    MatchingEvidence,
    MatchingProposal,
    MatchingRequest,
    PayerAlias,
    Receipt,
    SourceImport,
)

ALGORITHM = "exact-v1"
INVOICE_BUDGET = 1000
EVIDENCE_BUDGET = 100


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def lock_company(session, organization_id):
    key = int.from_bytes(hashlib.sha256(organization_id.bytes).digest()[:8], signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def owned(session, model, organization_id, record_id):
    record = session.scalar(
        select(model)
        .where(model.organization_id == organization_id, model.id == record_id)
        .with_for_update(read=True)
    )
    if record is None:
        raise HTTPException(404, "Record not found")
    return record


def source_valid(session, organization_id, record, kind, actual):
    source = owned(session, SourceImport, organization_id, record.source_import_id)
    if (
        source.status != "ACCEPTED"
        or source.kind != kind
        or hashlib.sha256(source.raw_bytes).hexdigest() != source.content_sha256
    ):
        return False
    try:
        rows = parse_csv(kind, source.raw_bytes)
        row = next((value for number, value in rows if number == record.source_row), None)
        return row is not None and canonical(row) == record.payload_sha256 == canonical(actual)
    except (ImportFailure, ValueError):
        return False


def bank_valid(session, organization_id, bank):
    try:
        actual = BankInput.model_validate(
            {
                "source_system": bank.source_system,
                "account_ref": bank.account_ref,
                "external_transaction_id": bank.external_transaction_id,
                "occurred_at": bank.occurred_at_source,
                "amount_paise": bank.amount_paise,
                "currency": bank.currency,
                "payer_name": bank.payer_name,
                "memo": bank.memo,
            }
        )
        return bank.occurred_at == timestamp(bank.occurred_at_source) and source_valid(
            session, organization_id, bank, "bank-transactions", actual
        )
    except ValueError:
        return False


def evidence_valid(evidence, receipt, bank, customers, invoices):
    owner = customers.get(evidence.customer_id)
    invoice = invoices.get(evidence.invoice_id)
    value = getattr(bank, evidence.source_field, "")
    return (
        evidence.receipt_version == receipt.version
        and owner is not None
        and evidence.customer_version == owner.version
        and evidence.source_import_id == bank.source_import_id
        and evidence.source_row == bank.source_row
        and value[evidence.start_offset : evidence.end_offset] == evidence.exact_quote
        and evidence.end_offset <= len(value)
        and (
            evidence.kind != "INVOICE_REFERENCE"
            or (
                invoice is not None
                and invoice.customer_id == evidence.customer_id
                and invoice.version == evidence.invoice_version
                and invoice.invoice_number == evidence.exact_quote
                and invoice_reference_span(
                    value, evidence.start_offset, evidence.end_offset, evidence.exact_quote
                )
            )
        )
    )


def build_snapshot(session, organization_id, receipt_id, *, advanced=False, invoice_budget=None):
    invoice_budget = INVOICE_BUDGET if invoice_budget is None else invoice_budget
    receipt = owned(session, Receipt, organization_id, receipt_id)
    bank = owned(session, BankTransaction, organization_id, receipt.bank_transaction_id)
    source_ok = bank_valid(session, organization_id, bank)
    evidence = session.scalars(
        select(MatchingEvidence)
        .where(
            MatchingEvidence.organization_id == organization_id,
            MatchingEvidence.receipt_id == receipt.id,
        )
        .order_by(MatchingEvidence.id)
        .limit(EVIDENCE_BUDGET + 1)
        .with_for_update(read=True)
    ).all()
    alias = (
        session.scalar(
            select(PayerAlias)
            .where(
                PayerAlias.organization_id == organization_id,
                PayerAlias.normalized_alias == " ".join(bank.payer_name.split()).casefold(),
            )
            .with_for_update(read=True)
        )
        if bank.payer_name
        else None
    )
    customer_ids = {item.customer_id for item in evidence}
    if alias is not None:
        customer_ids.add(alias.customer_id)
    customers = {
        row.id: row
        for row in session.scalars(
            select(Customer)
            .where(
                Customer.organization_id == organization_id,
                Customer.id.in_(customer_ids),
            )
            .with_for_update(read=True)
        )
    }
    referenced_ids = {item.invoice_id for item in evidence if item.invoice_id is not None}
    # A verified reference scopes intent. Without one inspect a bounded candidate set;
    # never infer intent merely from a unique amount.
    query = select(Invoice).where(Invoice.organization_id == organization_id)
    query = (
        query.where(Invoice.id.in_(referenced_ids))
        if referenced_ids
        else query.where(Invoice.customer_id.in_(customer_ids))
    )
    if advanced and not referenced_ids:
        query = query.where(
            Invoice.status == "OPEN",
            Invoice.open_amount_paise > 0,
            Invoice.currency == "INR",
            Invoice.issued_date <= bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date(),
        )
    invoice_rows = session.scalars(
        query.order_by(Invoice.id).limit(invoice_budget + 1).with_for_update(read=True)
    ).all()
    invoices = {row.id: row for row in invoice_rows}
    owners, references, basis = set(), set(), []
    invalid = not source_ok
    # Reverification of the identical source/target supersedes older versions.
    # Different customer/invoice targets remain independent conflicting evidence.
    active = {}
    for item in sorted(
        evidence,
        key=lambda row: (
            row.receipt_version,
            row.invoice_version or 0,
            row.customer_version,
            row.created_at,
            str(row.id),
        ),
    ):
        locator = (
            item.kind,
            item.customer_id,
            item.invoice_id,
            item.source_field,
            item.start_offset,
            item.end_offset,
            item.exact_quote,
        )
        active[locator] = item.id
    if alias is not None:
        customer = customers.get(alias.customer_id)
        try:
            alias_ok = customer is not None and bool(alias.verified_by and alias.evidence_reference)
            alias_ok = (
                alias_ok
                and alias.verified_at <= datetime.now(UTC)
                and source_valid(
                    session,
                    organization_id,
                    alias,
                    "payer-aliases",
                    AliasInput.model_validate(
                        {
                            "customer_reference": customer.external_reference,
                            "alias": alias.alias,
                            "verified_by": alias.verified_by,
                            "verified_at": alias.verified_at.isoformat(),
                            "evidence_reference": alias.evidence_reference,
                        }
                    ),
                )
            )
        except ValueError:
            alias_ok = False
        if alias_ok:
            owners.add(alias.customer_id)
            basis.append(
                {
                    "kind": "VERIFIED_PAYER_ALIAS",
                    "id": str(alias.id),
                    "version": alias.version,
                    "customer_id": str(alias.customer_id),
                    "source_import_id": str(alias.source_import_id),
                    "source_row": alias.source_row,
                    "payload_sha256": alias.payload_sha256,
                }
            )
        else:
            invalid = True
    for item in evidence:
        locator = (
            item.kind,
            item.customer_id,
            item.invoice_id,
            item.source_field,
            item.start_offset,
            item.end_offset,
            item.exact_quote,
        )
        if active[locator] != item.id:
            basis.append({"kind": item.kind, "id": str(item.id), "superseded": True})
            continue
        valid = evidence_valid(item, receipt, bank, customers, invoices)
        if valid:
            owners.add(item.customer_id)
            if item.invoice_id is not None:
                references.add(item.invoice_id)
        else:
            invalid = True
        basis.append(
            {
                "kind": item.kind,
                "id": str(item.id),
                "version": item.version,
                "customer_id": str(item.customer_id),
                "payload_sha256": item.payload_sha256,
                "valid": valid,
            }
        )
    decision = decide(
        unapplied_paise=receipt.unapplied_amount_paise,
        receipt_status=receipt.status,
        receipt_date=bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date(),
        customers=tuple(owners),
        references=tuple(references),
        invoices=tuple(
            InvoiceState(
                row.id,
                row.customer_id,
                row.version,
                row.open_amount_paise,
                row.status,
                row.issued_date,
                row.currency,
            )
            for row in invoice_rows
        ),
        stale_evidence=invalid,
        budget_exceeded=len(evidence) > EVIDENCE_BUDGET or len(invoice_rows) > INVOICE_BUDGET,
    )
    snapshot = {
        "algorithm": ALGORITHM,
        "receipt": {
            "id": str(receipt.id),
            "version": receipt.version,
            "amount_paise": receipt.amount_paise,
            "unapplied_amount_paise": receipt.unapplied_amount_paise,
            "status": receipt.status,
            "currency": receipt.currency,
        },
        "bank": {"id": str(bank.id), "payload_sha256": bank.payload_sha256, "valid": source_ok},
        "customers": [
            {
                "id": str(row.id),
                "version": row.version,
                "external_reference": row.external_reference,
            }
            for row in sorted(customers.values(), key=lambda row: str(row.id))
        ],
        "invoices": [
            {
                "id": str(row.id),
                "customer_id": str(row.customer_id),
                "version": row.version,
                "open_amount_paise": row.open_amount_paise,
                "original_amount_paise": row.original_amount_paise,
                "initial_open_amount_paise": row.initial_open_amount_paise,
                "source_import_id": str(row.source_import_id),
                "source_row": row.source_row,
                "payload_sha256": row.payload_sha256,
                "status": row.status,
                "issued_date": row.issued_date.isoformat(),
                "currency": row.currency,
            }
            for row in invoice_rows
        ],
        "basis": basis,
        "decision": json.loads(json.dumps(asdict(decision), default=str)),
    }
    if advanced:
        evidence_by_id = {str(row.id): row for row in evidence}
        for value in basis:
            row = evidence_by_id.get(value["id"])
            if row is not None:
                value.update(
                    invoice_id=str(row.invoice_id) if row.invoice_id else None,
                    receipt_version=row.receipt_version,
                    customer_version=row.customer_version,
                    invoice_version=row.invoice_version,
                    source_import_id=str(row.source_import_id),
                    source_row=row.source_row,
                    source_field=row.source_field,
                    start_offset=row.start_offset,
                    end_offset=row.end_offset,
                    exact_quote=row.exact_quote,
                )
        for value, row in zip(snapshot["invoices"], invoice_rows, strict=True):
            value["invoice_number"] = row.invoice_number
        snapshot.pop("decision")
        snapshot["validation"] = {
            "invalid_evidence": invalid,
            "customers": sorted(str(value) for value in owners),
            "references": sorted(str(value) for value in references),
            "input_limit_exceeded": len(evidence) > EVIDENCE_BUDGET
            or len(invoice_rows) > invoice_budget,
        }
    return receipt, bank, snapshot


def prior_request(session, organization_id, receipt_id, key, fingerprint):
    prior = session.scalar(
        select(MatchingRequest).where(
            MatchingRequest.organization_id == organization_id,
            MatchingRequest.idempotency_key == key,
        )
    )
    if prior is not None and (
        prior.receipt_id != receipt_id or prior.request_sha256 != fingerprint
    ):
        raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
    return prior


def register_evidence(session, organization_id, receipt_id, body, key, actor):
    lock_company(session, organization_id)
    receipt = owned(session, Receipt, organization_id, receipt_id)
    fingerprint = digest({"operation": "evidence", **body.model_dump(mode="json")})
    prior = prior_request(session, organization_id, receipt_id, key, fingerprint)
    if prior is not None:
        return owned(session, MatchingEvidence, organization_id, prior.evidence_id)
    customer = owned(session, Customer, organization_id, body.customer_id)
    bank = owned(session, BankTransaction, organization_id, receipt.bank_transaction_id)
    invoice = owned(session, Invoice, organization_id, body.invoice_id) if body.invoice_id else None
    if (
        receipt.version != body.expected_receipt_version
        or customer.version != body.expected_customer_version
        or (invoice is not None and invoice.version != body.expected_invoice_version)
    ):
        raise HTTPException(409, "STALE_EVIDENCE_VERSIONS")
    if invoice is not None and invoice.customer_id != customer.id:
        raise HTTPException(422, "INVOICE_CUSTOMER_MISMATCH")
    if body.source_import_id != bank.source_import_id or body.source_row != bank.source_row:
        raise HTTPException(422, "SOURCE_DOES_NOT_PERTAIN_TO_RECEIPT")
    source_value = getattr(bank, body.source_field)
    if body.end_offset > len(source_value):
        raise HTTPException(422, "INVALID_SOURCE_CITATION")
    quote = source_value[body.start_offset : body.end_offset]
    if quote != body.exact_quote or not bank_valid(session, organization_id, bank):
        raise HTTPException(422, "INVALID_SOURCE_CITATION")
    if invoice is not None and quote != invoice.invoice_number:
        raise HTTPException(422, "QUOTE_IS_NOT_INVOICE_REFERENCE")
    if invoice is not None and not invoice_reference_span(
        source_value, body.start_offset, body.end_offset, quote
    ):
        raise HTTPException(422, "INVOICE_REFERENCE_NOT_DELIMITED")
    record = session.scalar(
        select(MatchingEvidence).where(
            MatchingEvidence.organization_id == organization_id,
            MatchingEvidence.receipt_id == receipt_id,
            MatchingEvidence.payload_sha256 == fingerprint,
        )
    )
    if record is None:
        record = MatchingEvidence(
            organization_id=organization_id,
            receipt_id=receipt_id,
            customer_id=customer.id,
            invoice_id=body.invoice_id,
            receipt_version=receipt.version,
            customer_version=customer.version,
            invoice_version=body.expected_invoice_version,
            kind=body.kind,
            source_import_id=bank.source_import_id,
            source_row=bank.source_row,
            source_field=body.source_field,
            start_offset=body.start_offset,
            end_offset=body.end_offset,
            exact_quote=body.exact_quote,
            verified_by=actor,
            payload_sha256=fingerprint,
        )
        session.add(record)
        session.flush()
        from clearledger.case_events import matching_evidence_registered

        matching_evidence_registered(session, record, actor)
        event(
            session,
            organization_id,
            bank.source_import_id,
            actor,
            "matching.evidence_verified",
            record.id,
        )
    session.add(
        MatchingRequest(
            organization_id=organization_id,
            receipt_id=receipt_id,
            idempotency_key=key,
            request_sha256=fingerprint,
            evidence_id=record.id,
        )
    )
    session.commit()
    return record


def create_proposal(session, organization_id, receipt_id, body, key, actor):
    lock_company(session, organization_id)
    fingerprint = digest({"operation": "match", **body.model_dump(mode="json")})
    prior = prior_request(session, organization_id, receipt_id, key, fingerprint)
    receipt, bank, snapshot = build_snapshot(session, organization_id, receipt_id)
    snapshot_hash = digest(snapshot)
    if receipt.version != body.expected_receipt_version:
        raise HTTPException(409, "STALE_RECEIPT_VERSION")
    for invoice_id, version in body.expected_invoice_versions.items():
        invoice = owned(session, Invoice, organization_id, invoice_id)
        if invoice.version != version:
            raise HTTPException(409, "STALE_INVOICE_VERSION")
    if body.expected_snapshot_sha256 is not None and snapshot_hash != body.expected_snapshot_sha256:
        raise HTTPException(409, "STALE_SNAPSHOT")
    if prior is not None:
        proposal = owned(session, MatchingProposal, organization_id, prior.proposal_id)
        if proposal.snapshot_sha256 != snapshot_hash:
            raise HTTPException(409, "STALE_PROPOSAL")
        return proposal
    result = snapshot["decision"]
    if result["outcome"] == "EXACT_MATCH" and str(result["invoice_id"]) not in {
        str(i) for i in body.expected_invoice_versions
    }:
        raise HTTPException(409, "EXPECTED_INVOICE_VERSION_REQUIRED")
    proposal = session.scalar(
        select(MatchingProposal).where(
            MatchingProposal.organization_id == organization_id,
            MatchingProposal.receipt_id == receipt_id,
            MatchingProposal.snapshot_sha256 == snapshot_hash,
        )
    )
    if proposal is None:
        proposal = MatchingProposal(
            organization_id=organization_id,
            receipt_id=receipt_id,
            source_import_id=bank.source_import_id,
            customer_id=UUID(result["customers"][0]) if len(result["customers"]) == 1 else None,
            invoice_id=UUID(result["invoice_id"]) if result["invoice_id"] else None,
            amount_paise=result["amount_paise"],
            outcome=result["outcome"],
            snapshot_sha256=snapshot_hash,
            snapshot=snapshot,
            result=result,
        )
        session.add(proposal)
        session.flush()
        from clearledger.case_events import matching_proposed

        matching_proposed(session, proposal, actor)
        event(
            session,
            organization_id,
            bank.source_import_id,
            actor,
            "matching.proposal_created",
            proposal.id,
        )
    session.add(
        MatchingRequest(
            organization_id=organization_id,
            receipt_id=receipt_id,
            idempotency_key=key,
            request_sha256=fingerprint,
            proposal_id=proposal.id,
        )
    )
    session.commit()
    return proposal
