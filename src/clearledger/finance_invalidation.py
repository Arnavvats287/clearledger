"""Conservative invalidation grants no posting/review authority to source actors."""

from sqlalchemy import select

from clearledger.finance_models import FinanceAudit, FinanceProposal, FinanceProposalEvent

ACTIVE = {"DRAFT", "VALIDATED", "PENDING_APPROVAL", "APPROVED"}


def invalidate_rows(session, org, rows, actor, reason):
    for row in rows:
        if row.state not in ACTIVE:
            continue
        row.state, row.version = "INVALIDATED", row.version + 1
        session.add(
            FinanceProposalEvent(
                organization_id=org,
                proposal_id=row.id,
                proposal_version=row.version,
                state=row.state,
                actor=actor,
                reason=reason,
            )
        )
        session.add(
            FinanceAudit(
                organization_id=org,
                proposal_id=row.id,
                event_type="finance.invalidated",
                actor=actor,
                data={"reason": reason},
            )
        )
        session.flush()


def case_changed(session, org, case_ids, event):
    rows = list(
        session.scalars(
            select(FinanceProposal).where(
                FinanceProposal.organization_id == org,
                FinanceProposal.case_id.in_(case_ids),
                FinanceProposal.state.in_(ACTIVE),
            )
        )
    )
    invalidate_rows(
        session,
        org,
        rows,
        {"kind": "SYSTEM_INVALIDATION", "source_event_id": str(event.id)},
        "CASE_INPUT_CHANGED",
    )
