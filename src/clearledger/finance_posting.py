"""Transactional idempotent simulation. This service is never a graph node/tool."""

from datetime import UTC, datetime

from sqlalchemy import select, text

from clearledger.case_domain import CaseError
from clearledger.case_repository import scoped
from clearledger.finance_contract import Cash, ProposalInput
from clearledger.finance_domain import balanced, compose
from clearledger.finance_lifecycle import update as update_lifecycle
from clearledger.finance_models import (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    FinanceProposal,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)
from clearledger.finance_repository import (
    audit,
    check_identity,
    fingerprint,
    history,
    recognition,
    remember,
    replay,
)
from clearledger.finance_service import authorities, invalidate
from clearledger.finance_validation import compare_locked, evaluate
from clearledger.matching import lock_company, owned
from clearledger.models import Invoice, Receipt


def result(session, org, proposal):
    journals = list(
        session.scalars(
            select(LedgerJournal)
            .where(LedgerJournal.organization_id == org, LedgerJournal.proposal_id == proposal.id)
            .order_by(LedgerJournal.kind)
        )
    )
    return {
        "proposal_id": str(proposal.id),
        "proposal_version": proposal.version,
        "journal_ids": [str(j.id) for j in journals],
        "simulation_only": True,
        "state": "SIMULATED_POSTED",
    }


def post(session, org, identifier, body, key, principal, settings, verifier):
    principal.require("SIMULATE_POST", org)
    stamp = fingerprint("SIMULATE_POST", identifier, body, principal)
    previous = replay(session, org, key, stamp)
    if previous:
        return previous
    row = owned(session, FinanceProposal, org, identifier)
    case_id, payload = row.case_id, row.snapshot["body"]
    needs_preflight = row.state != "SIMULATED_POSTED"
    session.rollback()
    if needs_preflight:
        try:
            preflight, journals, treatments = evaluate(
                session.get_bind(), org, case_id, ProposalInput.model_validate(payload), settings
            )
        except Exception:
            invalidate(session, org, identifier, principal)
            raise CaseError("STALE_OR_UNVERIFIED_POSTING_INPUTS") from None
    session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
    session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
    lock_company(session, org)
    previous = replay(session, org, key, stamp)
    if previous:
        return previous
    row = session.scalar(
        select(FinanceProposal)
        .where(FinanceProposal.organization_id == org, FinanceProposal.id == identifier)
        .with_for_update()
    )
    if row is None:
        raise CaseError("FINANCE_PROPOSAL_NOT_FOUND", 404)
    if body.expected_snapshot_sha256 != row.snapshot_sha256:
        raise CaseError("POSTING_SNAPSHOT_MISMATCH")
    if row.state == "SIMULATED_POSTED":
        if body.expected_version not in {row.version, row.version - 1}:
            raise CaseError("STALE_POSTING_REPLAY")
        output = result(session, org, row)
        remember(session, org, key, stamp, "SIMULATE_POST", output, principal)
        audit(session, org, principal, "finance.post_replayed", proposal_id=row.id)
        session.commit()
        return output
    if row.version != body.expected_version or row.state != "APPROVED":
        raise CaseError("APPROVED_CURRENT_PROPOSAL_REQUIRED")
    compare_locked(session, org, row, preflight, settings)
    spec = authorities(session, org, row, verifier)
    check_identity(verifier, row.maker, "PROPOSE", org)
    approval = scoped(session, FinanceApproval, org, proposal_id=row.id)
    if (
        approval is None
        or approval.proposal_version != row.version
        or approval.snapshot_sha256 != row.snapshot_sha256
        or approval.expires_at <= datetime.now(UTC)
    ):
        raise CaseError("CURRENT_FINANCE_APPROVAL_REQUIRED")
    checker = check_identity(verifier, approval.approver, "APPROVE", org)
    if str(checker.subject) == row.maker["subject"]:
        raise CaseError("MAKER_CHECKER_REQUIRED", 403)
    cash = [Cash.model_validate(a) for a in payload["cash"]]
    expected_journals = compose(
        spec.chart,
        preflight["inputs"]["receipt_amount_paise"],
        cash,
        treatments,
        recognition(session, org, row.receipt_id) is not None,
    )
    if [j.model_dump(mode="json") for j in expected_journals] != row.journals or [
        t.model_dump(mode="json") for t in treatments
    ] != row.treatments:
        raise CaseError("JOURNAL_SEMANTIC_VALIDATION_FAILED")
    receipt = session.scalar(
        select(Receipt)
        .where(Receipt.organization_id == org, Receipt.id == row.receipt_id)
        .with_for_update()
    )
    invoices = {
        i.id: i
        for i in session.scalars(
            select(Invoice)
            .where(Invoice.organization_id == org, Invoice.id.in_([a.invoice_id for a in cash]))
            .order_by(Invoice.id)
            .with_for_update()
        )
    }
    customer_id = preflight["inputs"]["customer_id"]
    application = None
    for journal in expected_journals:
        balanced(journal, spec.chart)
        stored = LedgerJournal(
            organization_id=org,
            proposal_id=row.id,
            receipt_id=row.receipt_id,
            policy_id=row.policy_id,
            source_review_id=row.source_review_id,
            kind=journal.kind,
            actor=principal.provenance(),
            source_sha256=row.snapshot_sha256,
        )
        session.add(stored)
        session.flush()
        for number, line in enumerate(journal.lines, 1):
            session.add(
                LedgerLine(
                    organization_id=org,
                    journal_id=stored.id,
                    line_number=number,
                    **line.model_dump(),
                )
            )
            balance = scoped(session, AccountBalance, org, account_code=line.account_code)
            delta = line.debit_paise - line.credit_paise
            if balance is None:
                session.add(
                    AccountBalance(
                        organization_id=org, account_code=line.account_code, balance_paise=delta
                    )
                )
            else:
                updated = balance.balance_paise + delta
                if not -(2**63) <= updated <= 2**63 - 1:
                    raise CaseError("LEDGER_BALANCE_OVERFLOW")
                balance.balance_paise = updated
                balance.version += 1
        audit(session, org, principal, "finance.journal_recorded", journal_id=stored.id)
        if journal.kind == "APPLICATION":
            application = stored
    if application is None:
        raise CaseError("APPLICATION_JOURNAL_REQUIRED")
    for allocation in cash:
        invoice = invoices[allocation.invoice_id]
        noncash = sum(t.allowed_paise for t in treatments if t.invoice_id == invoice.id)
        if allocation.amount_paise + noncash > invoice.open_amount_paise:
            raise CaseError("INVOICE_OVERALLOCATION")
        invoice.open_amount_paise -= allocation.amount_paise + noncash
        invoice.status = "CLOSED" if invoice.open_amount_paise == 0 else "OPEN"
        invoice.version += 1
        session.add(
            CashAllocation(
                organization_id=org,
                proposal_id=row.id,
                journal_id=application.id,
                receipt_id=row.receipt_id,
                invoice_id=invoice.id,
                customer_id=customer_id,
                amount_paise=allocation.amount_paise,
            )
        )
    receipt.unapplied_amount_paise -= sum(a.amount_paise for a in cash)
    receipt.status = "FULLY_APPLIED" if receipt.unapplied_amount_paise == 0 else "PARTIALLY_APPLIED"
    receipt.version += 1
    for treatment in treatments:
        if treatment.allowed_paise:
            session.add(
                NoncashSettlement(
                    organization_id=org,
                    journal_id=application.id,
                    proposal_id=row.id,
                    policy_id=row.policy_id,
                    claim_id=treatment.claim_id,
                    invoice_id=treatment.invoice_id,
                    customer_id=customer_id,
                    rule_id=treatment.rule_id,
                    amount_paise=treatment.allowed_paise,
                    evidence_ids=[str(i) for i in treatment.evidence_ids],
                )
            )
    row.state, row.version = "SIMULATED_POSTED", row.version + 1
    history(session, org, row, principal, "ATOMIC_SIMULATED_POSTING")
    update_lifecycle(session, org, row, principal, settings)
    principal.require("SIMULATE_POST", org)
    output = result(session, org, row)
    remember(session, org, key, stamp, "SIMULATE_POST", output, principal)
    audit(
        session,
        org,
        principal,
        "finance.simulated_posted",
        proposal_id=row.id,
        data={"approval_id": str(approval.id), "source_snapshot_sha256": row.snapshot_sha256},
    )
    session.commit()
    return output
