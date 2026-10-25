"""Scoped snapshots, immutable command provenance and aggregate serialization."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from clearledger.case_domain import CaseError
from clearledger.case_models import CaseReceipt
from clearledger.case_repository import group_rows, members, root, scoped
from clearledger.case_sources import current_context, proposal_current
from clearledger.data_contract import InvoiceInput
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.finance_contract import PolicyInput
from clearledger.finance_models import (
    CashAllocation,
    FinanceAudit,
    FinanceCommand,
    FinancePolicy,
    FinanceProposalEvent,
    LedgerJournal,
    NoncashSettlement,
)
from clearledger.matching import bank_valid, digest, owned, source_valid
from clearledger.models import BankTransaction, Customer, Invoice, MatchingProposal, Receipt


def check_identity(verifier, provenance, permission, org):
    if verifier is None:
        raise CaseError("VERIFIED_FINANCE_IDENTITY_UNAVAILABLE", 503)
    try:
        principal = verifier.revalidate(provenance)
        if any(
            str(getattr(principal, field)) != str(provenance[field])
            for field in ("issuer", "subject", "organization_id", "authorization_version")
        ):
            raise ValueError
        principal.require(permission, org)
        return principal
    except Exception:
        raise CaseError("FINANCE_AUTHORITY_REVOKED", 403) from None


def fingerprint(operation, target, body, principal):
    return digest(
        {
            "operation": operation,
            "target": str(target),
            "body": body.model_dump(mode="json"),
            "identity": principal.identity,
        }
    )


def replay(session, org, key, fingerprint):
    command = scoped(session, FinanceCommand, org, idempotency_key=key)
    if command:
        if command.request_sha256 != fingerprint:
            raise CaseError("FINANCE_IDEMPOTENCY_CONFLICT")
        return command.result
    return None


def remember(session, org, key, fingerprint, operation, result, principal):
    session.add(
        FinanceCommand(
            organization_id=org,
            idempotency_key=key,
            request_sha256=fingerprint,
            operation=operation,
            result=result,
            actor=principal.provenance(),
        )
    )


def audit(session, org, principal, event, data=None, **sources):
    session.add(
        FinanceAudit(
            organization_id=org,
            event_type=event,
            actor=principal.provenance(),
            data=data or {},
            **sources,
        )
    )


def policy(session, org, identifier, *, active=True):
    record = owned(session, FinancePolicy, org, identifier)
    spec = PolicyInput.model_validate(record.spec)
    if record.content_sha256 != digest(record.spec):
        raise CaseError("POLICY_INTEGRITY_FAILURE")
    latest = session.scalar(
        select(FinancePolicy.id)
        .where(FinancePolicy.organization_id == org, FinancePolicy.reference == record.reference)
        .order_by(FinancePolicy.policy_version.desc())
        .limit(1)
    )
    if active and (
        latest != record.id
        or not spec.enabled
        or not spec.effective_from
        <= datetime.now(ZoneInfo("Asia/Kolkata")).date()
        <= spec.effective_to
    ):
        raise CaseError("POLICY_NOT_CURRENT")
    return record, spec


def history(session, org, row, principal, reason):
    session.add(
        FinanceProposalEvent(
            organization_id=org,
            proposal_id=row.id,
            proposal_version=row.version,
            state=row.state,
            actor=principal.provenance(),
            reason=reason,
        )
    )
    session.flush()


def conservation(session, org, receipt, invoices):
    cash = session.scalar(
        select(func.coalesce(func.sum(CashAllocation.amount_paise), 0)).where(
            CashAllocation.organization_id == org, CashAllocation.receipt_id == receipt.id
        )
    )
    if receipt.amount_paise != receipt.unapplied_amount_paise + cash:
        raise CaseError("RECEIPT_CONSERVATION_FAILURE")
    for invoice in invoices:
        paid = session.scalar(
            select(func.coalesce(func.sum(CashAllocation.amount_paise), 0)).where(
                CashAllocation.organization_id == org, CashAllocation.invoice_id == invoice.id
            )
        )
        noncash = session.scalar(
            select(func.coalesce(func.sum(NoncashSettlement.amount_paise), 0)).where(
                NoncashSettlement.organization_id == org, NoncashSettlement.invoice_id == invoice.id
            )
        )
        if invoice.initial_open_amount_paise != invoice.open_amount_paise + paid + noncash:
            raise CaseError("INVOICE_CONSERVATION_FAILURE")


def base(session, org, case_id, body, settings):
    case = root(session, org, case_id)
    store = EvidenceOriginals(settings.document_root)
    context = current_context(session, org, case, store)
    if (
        case.id != case_id
        or case.version != body.expected_case_version
        or case.context_sha256 != body.expected_context_sha256
        or digest(context) != case.context_sha256
    ):
        raise CaseError("STALE_FINANCE_CASE")
    if not case.customer_id:
        raise CaseError("VERIFIED_FINANCE_CUSTOMER_REQUIRED")
    match = owned(session, MatchingProposal, org, body.matching_proposal_id)
    if match.receipt_id not in {
        r.receipt_id for r in group_rows(session, CaseReceipt, org, members(session, org, case))
    }:
        raise CaseError("MATCHING_RECEIPT_OUTSIDE_CASE", 404)
    if not proposal_current(session, org, match, settings) or match.customer_id != case.customer_id:
        raise CaseError("STALE_OR_FOREIGN_MATCHING_PROPOSAL")
    if match.outcome == "EXACT_MATCH":
        bounds = {match.invoice_id: match.amount_paise}
    elif (
        match.outcome == "UNIQUE"
        and match.result.get("intent_verified") is True
        and match.result.get("search_exhaustive") is True
        and len(match.result.get("candidates", [])) == 1
    ):
        from uuid import UUID

        bounds = {
            UUID(a["invoice_id"]): a["amount_paise"]
            for a in match.result["candidates"][0]["allocations"]
        }
    else:
        raise CaseError("SUPPORTED_PAYMENT_INTENT_REQUIRED")
    receipt = owned(session, Receipt, org, match.receipt_id)
    bank = owned(session, BankTransaction, org, receipt.bank_transaction_id)
    if (
        not bank_valid(session, org, bank)
        or receipt.currency != "INR"
        or bank.occurred_at > datetime.now(UTC)
    ):
        raise CaseError("BANK_SOURCE_INVALID")
    customer = owned(session, Customer, org, case.customer_id)
    invoices = []
    if len({a.invoice_id for a in body.cash}) != len(body.cash):
        raise CaseError("DUPLICATE_FINANCE_INVOICE", 422)
    for allocation in sorted(body.cash, key=lambda a: a.invoice_id):
        invoice = owned(session, Invoice, org, allocation.invoice_id)
        if (
            invoice.customer_id != customer.id
            or invoice.status != "OPEN"
            or invoice.currency != "INR"
            or allocation.amount_paise > min(invoice.open_amount_paise, bounds.get(invoice.id, 0))
        ):
            raise CaseError("INVOICE_ALLOCATION_NOT_SUPPORTED")
        actual = InvoiceInput(
            customer_reference=customer.external_reference,
            invoice_number=invoice.invoice_number,
            issued_date=invoice.issued_date.isoformat(),
            due_date=invoice.due_date.isoformat(),
            original_amount_paise=invoice.original_amount_paise,
            open_amount_paise=invoice.initial_open_amount_paise,
            currency=invoice.currency,
        )
        if not source_valid(session, org, invoice, "invoices", actual):
            raise CaseError("INVOICE_SOURCE_INVALID")
        invoices.append(invoice)
    if sum(a.amount_paise for a in body.cash) > receipt.unapplied_amount_paise:
        raise CaseError("INSUFFICIENT_AVAILABLE_CASH")
    conservation(session, org, receipt, invoices)
    value = {
        "case_id": str(case.id),
        "case_version": case.version,
        "context_sha256": case.context_sha256,
        "customer_id": str(customer.id),
        "customer_version": customer.version,
        "receipt_id": str(receipt.id),
        "receipt_version": receipt.version,
        "receipt_amount_paise": receipt.amount_paise,
        "available_cash_paise": receipt.unapplied_amount_paise,
        "bank_id": str(bank.id),
        "bank_source_sha256": bank.payload_sha256,
        "matching_proposal_id": str(match.id),
        "matching_sha256": match.snapshot_sha256,
        "cash": [a.model_dump(mode="json") for a in body.cash],
        "invoices": [
            {
                "id": str(i.id),
                "version": i.version,
                "open_paise": i.open_amount_paise,
                "source_sha256": i.payload_sha256,
                "original_amount_paise": i.original_amount_paise,
            }
            for i in invoices
        ],
    }
    return case, receipt, bank, invoices, value


def recognition(session, org, receipt_id):
    return scoped(session, LedgerJournal, org, receipt_id=receipt_id, kind="BANK")
