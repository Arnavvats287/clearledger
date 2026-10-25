"""Simulation-only authenticated boundary, independent of document bearer access."""

from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import select

from clearledger.api import DB, company_scope
from clearledger.case_api import Limit, Offset
from clearledger.evidence_api import EvidenceRoute
from clearledger.finance_contract import (
    ApprovalInput,
    CommandInput,
    PolicyInput,
    ProposalInput,
    ProposalView,
    SourceReviewInput,
)
from clearledger.finance_identity import Identity
from clearledger.finance_models import (
    AccountBalance,
    FinanceAudit,
    FinancePolicy,
    FinanceProposal,
    LedgerJournal,
    LedgerLine,
)
from clearledger.finance_posting import post
from clearledger.finance_service import (
    change,
    create,
    publish_policy,
    request_approval,
    review_sources,
    view,
)
from clearledger.matching_api import Key

router = APIRouter(tags=["accounting-simulation"], route_class=EvidenceRoute)


def scope(request, session, principal, permission):
    org = company_scope(request, session)
    principal.require(permission, org)
    return org


def proposal(session, org, identifier):
    from fastapi import HTTPException

    row = session.scalar(
        select(FinanceProposal).where(
            FinanceProposal.organization_id == org, FinanceProposal.id == identifier
        )
    )
    if row is None:
        raise HTTPException(404, "Financial proposal not found")
    return row


@router.post("/finance/policies")
def policy_create(body: PolicyInput, key: Key, session: DB, identity: Identity, request: Request):
    return publish_policy(
        session, scope(request, session, identity, "REVIEW_POLICY"), body, key, identity
    )


@router.get("/finance/policies")
def policies(
    session: DB, identity: Identity, request: Request, limit: Limit = 100, offset: Offset = 0
):
    org = scope(request, session, identity, "FINANCE_READ")
    return [
        {
            "id": row.id,
            "spec": row.spec,
            "content_sha256": row.content_sha256,
            "reviewer": row.reviewer,
            "reviewed_rules": [
                {
                    **rule,
                    "verified_by": row.reviewer,
                    "verification_date": row.created_at.date().isoformat(),
                    "policy_version_id": str(row.id),
                }
                for rule in row.spec["rules"]
            ],
            "created_at": row.created_at,
        }
        for row in session.scalars(
            select(FinancePolicy)
            .where(FinancePolicy.organization_id == org)
            .order_by(FinancePolicy.created_at.desc(), FinancePolicy.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.post("/cases/{case_id}/finance-source-reviews")
def source_review(
    case_id: UUID,
    body: SourceReviewInput,
    key: Key,
    session: DB,
    identity: Identity,
    request: Request,
):
    org = scope(request, session, identity, "REVIEW_SOURCES")
    return review_sources(session, org, case_id, body, key, identity, request.app.state.settings)


@router.post("/cases/{case_id}/journal-proposals", response_model=ProposalView)
def propose(
    case_id: UUID, body: ProposalInput, key: Key, session: DB, identity: Identity, request: Request
):
    org = scope(request, session, identity, "PROPOSE")
    row = create(
        session,
        org,
        case_id,
        body,
        key,
        identity,
        request.app.state.settings,
        request.app.state.finance_identity_verifier,
    )
    return view(session, org, row, request.app.state.settings)


@router.get("/journal-proposals/{identifier}", response_model=ProposalView)
def get_proposal(identifier: UUID, session: DB, identity: Identity, request: Request):
    org = scope(request, session, identity, "FINANCE_READ")
    return view(session, org, proposal(session, org, identifier), request.app.state.settings)


@router.post("/journal-proposals/{identifier}/request-approval", response_model=ProposalView)
def submit(
    identifier: UUID,
    body: CommandInput,
    key: Key,
    session: DB,
    identity: Identity,
    request: Request,
):
    org = scope(request, session, identity, "PROPOSE")
    row = request_approval(
        session,
        org,
        identifier,
        body,
        key,
        identity,
        request.app.state.settings,
        request.app.state.finance_identity_verifier,
    )
    return view(session, org, row, request.app.state.settings)


@router.post("/journal-proposals/{identifier}/review", response_model=ProposalView)
def approve(
    identifier: UUID,
    body: ApprovalInput,
    key: Key,
    session: DB,
    identity: Identity,
    request: Request,
):
    org = scope(request, session, identity, "APPROVE")
    from clearledger.case_domain import CaseError

    if body.decision == "APPROVE" and body.reason != "VERIFIED_SIMULATION":
        raise CaseError("VERIFIED_APPROVAL_REASON_REQUIRED", 422)
    row = change(
        session,
        org,
        identifier,
        body,
        key,
        identity,
        request.app.state.settings,
        request.app.state.finance_identity_verifier,
        "APPROVED" if body.decision == "APPROVE" else "REJECTED",
    )
    return view(session, org, row, request.app.state.settings)


@router.post("/journal-proposals/{identifier}/simulate-post")
def simulate_post(
    identifier: UUID,
    body: CommandInput,
    key: Key,
    session: DB,
    identity: Identity,
    request: Request,
):
    org = scope(request, session, identity, "SIMULATE_POST")
    return post(
        session,
        org,
        identifier,
        body,
        key,
        identity,
        request.app.state.settings,
        request.app.state.finance_identity_verifier,
    )


@router.get("/finance/journals")
def journals(
    session: DB, identity: Identity, request: Request, limit: Limit = 100, offset: Offset = 0
):
    org = scope(request, session, identity, "FINANCE_READ")
    rows = list(
        session.scalars(
            select(LedgerJournal)
            .where(LedgerJournal.organization_id == org)
            .order_by(LedgerJournal.created_at, LedgerJournal.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "proposal_id": row.proposal_id,
            "receipt_id": row.receipt_id,
            "source_snapshot_sha256": row.source_sha256,
            "lines": [
                {
                    "account_code": line.account_code,
                    "account_role": line.account_role,
                    "invoice_id": line.invoice_id,
                    "debit_paise": line.debit_paise,
                    "credit_paise": line.credit_paise,
                }
                for line in session.scalars(
                    select(LedgerLine)
                    .where(LedgerLine.organization_id == org, LedgerLine.journal_id == row.id)
                    .order_by(LedgerLine.line_number)
                )
            ],
            "simulation_only": True,
        }
        for row in rows
    ]


@router.get("/finance/account-balances")
def balances(
    session: DB, identity: Identity, request: Request, limit: Limit = 100, offset: Offset = 0
):
    org = scope(request, session, identity, "FINANCE_READ")
    return [
        {
            "account_code": row.account_code,
            "net_simulated_movement_paise": row.balance_paise,
            "version": row.version,
        }
        for row in session.scalars(
            select(AccountBalance)
            .where(AccountBalance.organization_id == org)
            .order_by(AccountBalance.account_code)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/finance/audit")
def events(
    session: DB, identity: Identity, request: Request, limit: Limit = 100, offset: Offset = 0
):
    org = scope(request, session, identity, "FINANCE_READ")
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor": row.actor,
            "data": row.data,
            "policy_id": row.policy_id,
            "source_review_id": row.source_review_id,
            "proposal_id": row.proposal_id,
            "journal_id": row.journal_id,
            "created_at": row.created_at,
        }
        for row in session.scalars(
            select(FinanceAudit)
            .where(FinanceAudit.organization_id == org)
            .order_by(FinanceAudit.created_at, FinanceAudit.id)
            .offset(offset)
            .limit(limit)
        )
    ]
