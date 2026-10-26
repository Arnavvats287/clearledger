"""Role-checked nonfinancial correlation task and immutable decision APIs."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from clearledger.api import DB
from clearledger.case_api import Limit, Offset
from clearledger.case_domain import CaseError
from clearledger.case_models import CaseDocument
from clearledger.case_repository import members, root
from clearledger.correlation_contract import DecisionInput, DecisionView, RefreshInput, TaskView
from clearledger.correlation_models import CorrelationDecision, CorrelationTask
from clearledger.correlation_service import decide, decision_view, refresh, task_view
from clearledger.document_contract import ExtractionError
from clearledger.document_runtime import LocalOriginals
from clearledger.evidence_api import EvidenceRoute
from clearledger.matching import owned
from clearledger.matching_api import Key
from clearledger.review_identity import ReviewIdentity
from clearledger.review_models import ReviewAudit

router = APIRouter(prefix="/review", tags=["correlation-review"], route_class=EvidenceRoute)


@router.get("/cases/{case_id}/correlation-tasks", response_model=list[TaskView])
def tasks(
    case_id: UUID,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
    limit: Limit = 20,
    offset: Offset = 0,
    history: bool = Query(False),
):
    identity.require("READ")
    org = identity.organization_id
    ids = members(session, org, root(session, org, case_id))
    statement = select(CorrelationTask).where(
        CorrelationTask.organization_id == org, CorrelationTask.case_id.in_(ids)
    )
    if not history:
        statement = statement.distinct(CorrelationTask.document_id).order_by(
            CorrelationTask.document_id,
            CorrelationTask.created_at.desc(),
            CorrelationTask.id.desc(),
        )
    else:
        statement = statement.order_by(CorrelationTask.created_at.desc(), CorrelationTask.id.desc())
    return [
        task_view(
            session,
            org,
            task,
            request.app.state.settings,
            LocalOriginals(request.app.state.settings.document_root),
        )
        for task in session.scalars(statement.offset(offset).limit(limit))
    ]


@router.post("/cases/{case_id}/correlation-tasks/refresh", response_model=list[TaskView])
def refresh_tasks(
    case_id: UUID,
    body: RefreshInput,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
    key: Key,
):
    identity.require("WORK")
    org = identity.organization_id
    case = root(session, org, case_id)
    store = LocalOriginals(request.app.state.settings.document_root)
    links = list(
        session.scalars(
            select(CaseDocument)
            .where(
                CaseDocument.organization_id == org,
                CaseDocument.case_id.in_(members(session, org, case)),
            )
            .limit(101)
        )
    )
    if len(links) > 100:
        raise CaseError("CORRELATION_DOCUMENT_LIMIT")
    rows = [
        refresh(
            session,
            org,
            case,
            link.document_id,
            request.app.state.settings,
            store,
            identity.identity,
        )
        for link in links
    ]
    session.commit()
    return [task_view(session, org, row, request.app.state.settings, store) for row in rows if row]


@router.get("/correlation-tasks/{task_id}/decisions", response_model=list[DecisionView])
def decisions(task_id: UUID, session: DB, identity: ReviewIdentity, request: Request):
    identity.require("READ")
    owned(session, CorrelationTask, identity.organization_id, task_id)
    return [
        decision_view(
            row,
            session,
            identity.organization_id,
            request.app.state.settings,
            LocalOriginals(request.app.state.settings.document_root),
        )
        for row in session.scalars(
            select(CorrelationDecision).where(
                CorrelationDecision.organization_id == identity.organization_id,
                CorrelationDecision.task_id == task_id,
            )
        )
    ]


@router.post("/correlation-tasks/{task_id}/decision", response_model=DecisionView)
def decision(
    task_id: UUID,
    body: DecisionInput,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
    key: Key,
):
    try:
        row = decide(
            session,
            identity.organization_id,
            task_id,
            body,
            key,
            identity,
            request.app.state.settings,
            request.app.state.finance_identity_verifier,
            LocalOriginals(request.app.state.settings.document_root),
        )
    except (CaseError, HTTPException, ExtractionError) as error:
        session.rollback()
        session.add(
            ReviewAudit(
                organization_id=identity.organization_id,
                actor=identity.provenance,
                operation="CORRELATION",
                outcome="DENIED",
                code=error.code if isinstance(error, CaseError) else "CORRELATION_DENIED",
                target_id=task_id,
            )
        )
        session.commit()
        raise
    return decision_view(
        row,
        session,
        identity.organization_id,
        request.app.state.settings,
        LocalOriginals(request.app.state.settings.document_root),
    )
