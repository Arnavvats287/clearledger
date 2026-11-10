"""Bounded public read projections built from the existing case views."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from clearledger import case_api, correlation_api, evidence_api, investigation_api
from clearledger.api import DB
from clearledger.document_api import DocumentView
from clearledger.investigation_models import InvestigationFinding, InvestigationTrace
from clearledger.models import BankTransaction, Customer, Document, Invoice, Receipt
from clearledger.review_identity import Reviewer, demo_session
from clearledger.views import CustomerView, InvoiceView, ReceiptView

# Only the outer portfolio gateway forwards to these loopback routes. Like the
# other /review routes, they perform their own reviewer authentication.
router = APIRouter(
    prefix="/review/portfolio", include_in_schema=False, route_class=case_api.SafeCaseRoute
)
REGISTER_CASES = 20
REGISTER_RECORDS = 100
SUMMARY_NODES = ("investigator_synthesize", "human_review_or_request_evidence")


def read_auditor(request: Request, session: DB) -> Reviewer:
    # Authenticate the same server-owned demo user under the existing shared
    # case read lock. Exclusive admission would block concurrent snapshots.
    org = case_api.scoped_access(request, session)
    user, _ = demo_session(request, session, org)
    if user.role != "AUDITOR":
        raise HTTPException(403, "PORTFOLIO_AUDITOR_REQUIRED")
    return Reviewer(user.id, org, "AUDITOR", f"local-demo:{user.id}", {})


Auditor = Annotated[Reviewer, Depends(read_auditor)]


def records(session, org, model, ids=None):
    query = select(model).where(model.organization_id == org)
    if ids is not None:
        query = query.where(model.id.in_(ids))
    return session.scalars(query.order_by(model.created_at, model.id).limit(REGISTER_RECORDS))


def assessment_step(row):
    if row.node == "human_review_or_request_evidence":
        return {"node": row.node, "metadata": {"next_action": row.data.get("next_action")}}
    synthesis = row.data.get("synthesis") or {}
    return {
        "node": row.node,
        "metadata": {
            "fallback": row.data.get("fallback"),
            "synthesis": {
                field: synthesis.get(field)
                for field in ("state", "next_action", "missing_evidence_types")
            },
        },
    }


def bundle(session, reviewer, request, case, *, summary=False):
    org = reviewer.organization_id
    case_id = case.id
    claims = case_api.claims(case_id, session, org, request, limit=20)
    runs = investigation_api.listing(case_id, session, org, request, limit=20)
    tasks = correlation_api.tasks(case_id, session, reviewer, request, history=False)
    current = next((run for run in runs if not run.is_stale), runs[0] if runs else None)
    findings, trace = [], []
    if current and summary:
        # The queue uses persisted decisions only. Full trace and citation
        # checks belong to the individual case, never to initial navigation.
        findings = [
            {field: row.value[field] for field in ("state", "unknowns", "next_action")}
            for row in session.scalars(
                select(InvestigationFinding)
                .where(
                    InvestigationFinding.organization_id == org,
                    InvestigationFinding.run_id == current.id,
                )
                .order_by(InvestigationFinding.claim_id)
                .limit(1)
            )
        ]
        trace = [
            assessment_step(row)
            for row in session.scalars(
                select(InvestigationTrace)
                .where(
                    InvestigationTrace.organization_id == org,
                    InvestigationTrace.run_id == current.id,
                    InvestigationTrace.node.in_(SUMMARY_NODES),
                )
                .order_by(InvestigationTrace.created_at, InvestigationTrace.id)
                .limit(20)
            )
        ]
    elif current:
        findings = investigation_api.findings(current.id, session, org, request, Response())
        trace = investigation_api.trace(current.id, session, org)
    return {
        "case": case,
        "claims": claims,
        "runs": runs,
        "tasks": tasks,
        "findings": findings,
        "trace": trace,
    }


@router.get("/bootstrap")
def bootstrap(session: DB, reviewer: Auditor, request: Request):
    org = reviewer.organization_id
    cases = case_api.case_list(session, org, request, limit=REGISTER_CASES)
    return {
        "customers": [CustomerView.model_validate(row) for row in records(session, org, Customer)],
        "invoices": [InvoiceView.model_validate(row) for row in records(session, org, Invoice)],
        "receipts": [ReceiptView.model_validate(row) for row in records(session, org, Receipt)],
        "documents": [DocumentView.model_validate(row) for row in records(session, org, Document)],
        "banks": [
            {
                "id": row.id,
                "external_transaction_id": row.external_transaction_id,
                "payer_name": row.payer_name,
                "occurred_at_source": row.occurred_at_source,
            }
            for row in records(session, org, BankTransaction)
        ],
        "cases": [bundle(session, reviewer, request, case, summary=True) for case in cases],
    }


@router.get("/cases/{case_id}")
def case_detail(case_id: UUID, session: DB, reviewer: Auditor, request: Request):
    org = reviewer.organization_id
    case = case_api.case_get(case_id, session, org, request)
    data = bundle(session, reviewer, request, case)
    citations = dict.fromkeys(c.record_id for f in data["findings"] for c in f.citations)
    customer = next(iter(records(session, org, Customer, [case.customer_id])), None)
    return {
        "b": data,
        "invoices": [
            InvoiceView.model_validate(row)
            for row in records(session, org, Invoice, case.invoice_ids)
        ],
        "receipts": [
            ReceiptView.model_validate(row)
            for row in records(session, org, Receipt, case.receipt_ids)
        ],
        "docs": [
            DocumentView.model_validate(row)
            for row in records(session, org, Document, case.document_ids)
        ],
        "customer": CustomerView.model_validate(customer) if customer else None,
        "sources": [
            evidence_api.pointer(
                case.id,
                record_id,
                session,
                org,
                request,
                case.version,
                case.context_sha256,
                case.customer_id,
            )
            for record_id in list(citations)[:20]
            if case.customer_id
        ],
    }
