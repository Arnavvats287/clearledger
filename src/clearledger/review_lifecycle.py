"""Operational closure never settles balances or reverses a journal."""

from sqlalchemy import select

from clearledger.case_domain import CASE_EDGES, CaseError, CaseState
from clearledger.case_models import CaseInvoice, CaseReceipt, Claim, DomainEvent, OutboxEvent
from clearledger.case_repository import group_rows, members
from clearledger.case_service import claim_view
from clearledger.finance_models import FinanceProposal
from clearledger.matching import owned
from clearledger.models import Invoice, Receipt
from clearledger.review_models import ReviewAction


def closure_facts(session, org, case, store, reviewer):
    reviewer.require("CLOSE")
    ids = members(session, org, case)
    if case.customer_id is None or case.attention_codes:
        raise CaseError("CLOSURE_CUSTOMER_OR_ATTENTION_UNRESOLVED")
    if (
        CaseState.CLOSED not in CASE_EDGES[CaseState(case.state)]
        and CaseState.READY_TO_APPLY not in CASE_EDGES[CaseState(case.state)]
        and case.state != "AWAITING_EVIDENCE"
    ):
        raise CaseError("INVALID_CASE_CLOSURE_TRANSITION")
    invoices = [
        owned(session, Invoice, org, identifier)
        for identifier in sorted(
            {row.invoice_id for row in group_rows(session, CaseInvoice, org, ids)}
        )
    ]
    receipts = [
        owned(session, Receipt, org, row.receipt_id)
        for row in group_rows(session, CaseReceipt, org, ids)
    ]
    if (
        not invoices
        or not receipts
        or any(i.customer_id != case.customer_id or i.open_amount_paise != 0 for i in invoices)
        or any(r.unapplied_amount_paise != 0 or r.status != "FULLY_APPLIED" for r in receipts)
    ):
        raise CaseError("CLOSURE_FINANCIAL_OUTSTANDING")
    claims = group_rows(session, Claim, org, ids)
    if any(
        c.state != "RESOLVED" or not claim_view(session, org, c, store).source_current
        for c in claims
    ):
        raise CaseError("CLOSURE_MANDATORY_CLAIMS_UNRESOLVED")
    proposals = list(
        session.scalars(
            select(FinanceProposal)
            .where(FinanceProposal.organization_id == org, FinanceProposal.case_id.in_(ids))
            .limit(2001)
        )
    )
    if len(proposals) > 2000 or not any(p.state == "SIMULATED_POSTED" for p in proposals):
        raise CaseError("CLOSURE_POSTING_PROOF_REQUIRED")
    if any(p.state not in {"SIMULATED_POSTED", "REJECTED", "INVALIDATED"} for p in proposals):
        raise CaseError("CLOSURE_PENDING_PROPOSALS")
    if any(
        p.state == "SIMULATED_POSTED" and str(reviewer.subject) == p.maker["subject"]
        for p in proposals
    ):
        raise CaseError("CLOSURE_MAKER_CHECKER_REQUIRED", 403)
    pending = session.scalar(
        select(OutboxEvent.id)
        .join(
            DomainEvent,
            (DomainEvent.organization_id == OutboxEvent.organization_id)
            & (DomainEvent.id == OutboxEvent.event_id),
        )
        .where(
            OutboxEvent.organization_id == org,
            DomainEvent.case_id.in_(ids),
            OutboxEvent.status != "DELIVERED",
        )
        .limit(1)
    )
    if pending is not None:
        raise CaseError("CLOSURE_PENDING_WORK")
    actions = list(
        session.scalars(
            select(ReviewAction)
            .where(ReviewAction.organization_id == org, ReviewAction.case_id.in_(ids))
            .limit(2001)
        )
    )
    if len(actions) > 2000:
        raise CaseError("CLOSURE_REVIEW_HISTORY_BUDGET")
    replied = {a.in_reply_to for a in actions if a.kind == "RESPONSE"}
    if any(a.kind == "REQUEST_EVIDENCE" and a.id not in replied for a in actions):
        raise CaseError("CLOSURE_MANDATORY_RESPONSE_MISSING")
    return {
        "invoices": [{"id": str(i.id), "version": i.version, "open_paise": 0} for i in invoices],
        "receipts": [
            {"id": str(r.id), "version": r.version, "unapplied_paise": 0} for r in receipts
        ],
        "claims": [{"id": str(c.id), "version": c.version} for c in claims],
        "posted_proposals": [str(p.id) for p in proposals if p.state == "SIMULATED_POSTED"],
    }
