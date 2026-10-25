"""Authenticated workflow commands and bounded, sanitized read models."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from clearledger.api import DB
from clearledger.case_api import Limit, Offset, Scope
from clearledger.case_repository import root
from clearledger.evidence_api import EvidenceRoute
from clearledger.investigation_contract import FindingView, ResumeInput, RunView, StartInput
from clearledger.investigation_models import Investigation, InvestigationFinding, InvestigationTrace
from clearledger.investigation_service import finding_current, start, view
from clearledger.matching import owned
from clearledger.matching_api import Actor, Key

router = APIRouter(tags=["investigations"], route_class=EvidenceRoute)


@router.post("/investigations/{run_id}/resume", response_model=RunView)
def resume(
    run_id: UUID, body: ResumeInput, session: DB, org: Scope, actor: Actor, request: Request
):
    from sqlalchemy import text

    from clearledger.case_domain import CaseError
    from clearledger.case_events import publish
    from clearledger.case_models import DomainEvent, OutboxEvent
    from clearledger.investigation_service import current
    from clearledger.matching import lock_company

    lock_company(session, org)
    run = owned(session, Investigation, org, run_id)
    if run.version != body.expected_run_version:
        raise CaseError("STALE_INVESTIGATION_VERSION")
    if run.status not in {"RUNNING", "QUEUED"}:
        raise CaseError("INVESTIGATION_ALREADY_FINISHED")
    if not current(session, org, run, request.app.state.settings):
        raise CaseError("STALE_INVESTIGATION_INPUTS")
    row = session.scalar(
        select(OutboxEvent)
        .join(DomainEvent, DomainEvent.id == OutboxEvent.event_id)
        .where(
            OutboxEvent.organization_id == org,
            DomainEvent.organization_id == org,
            DomainEvent.event_type == "investigation.requested",
            DomainEvent.payload["run_id"].astext == str(run_id),
        )
        .with_for_update()
    )
    now = session.scalar(text("SELECT clock_timestamp()"))
    if row is None or row.status not in {"PENDING", "RETRY", "LEASED"}:
        raise CaseError("INVESTIGATION_DELIVERY_NOT_RESUMABLE")
    if row.status == "LEASED" and row.lease_until > now:
        raise CaseError("INVESTIGATION_WORKER_ACTIVE")
    if row.status in {"PENDING", "RETRY"}:
        row.available_at = now
        row.version += 1
    publish(
        session,
        org,
        "investigation.resume_requested",
        "case_id",
        run.case_id,
        actor,
        {"run_id": str(run.id), "run_version": run.version},
        queued=False,
        key={"resume": str(run.id), "version": run.version},
    )
    session.commit()
    return view(session, org, run, request.app.state.settings)


@router.post("/cases/{case_id}/investigations", response_model=RunView)
def create(
    case_id: UUID,
    body: StartInput,
    session: DB,
    org: Scope,
    key: Key,
    actor: Actor,
    request: Request,
):
    settings = request.app.state.settings
    provider = getattr(request.app.state, "investigation_provider", None)
    run = start(session, org, case_id, body, key, actor, settings, provider)
    return view(session, org, run, settings)


@router.get("/cases/{case_id}/investigations", response_model=list[RunView])
def listing(
    case_id: UUID, session: DB, org: Scope, request: Request, limit: Limit = 100, offset: Offset = 0
):
    case = root(session, org, case_id)
    rows = session.scalars(
        select(Investigation)
        .where(Investigation.organization_id == org, Investigation.case_id == case.id)
        .order_by(Investigation.created_at.desc(), Investigation.id)
        .offset(offset)
        .limit(limit)
    )
    return [view(session, org, row, request.app.state.settings) for row in rows]


@router.get("/investigations/{run_id}", response_model=RunView)
def get_run(run_id: UUID, session: DB, org: Scope, request: Request):
    return view(
        session, org, owned(session, Investigation, org, run_id), request.app.state.settings
    )


@router.get("/investigations/{run_id}/findings", response_model=list[FindingView])
def findings(run_id: UUID, session: DB, org: Scope, request: Request, response: Response):
    run = owned(session, Investigation, org, run_id)
    response.headers["X-Investigation-Stale"] = str(
        view(session, org, run, request.app.state.settings).is_stale
    ).lower()
    return [
        FindingView(
            **row.value, is_current=finding_current(session, org, row, request.app.state.settings)
        )
        for row in session.scalars(
            select(InvestigationFinding)
            .where(
                InvestigationFinding.organization_id == org, InvestigationFinding.run_id == run.id
            )
            .order_by(InvestigationFinding.claim_id)
            .limit(20)
        )
    ]


@router.get("/investigations/{run_id}/trace")
def trace(run_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    owned(session, Investigation, org, run_id)
    return [
        {"id": row.id, "node": row.node, "metadata": row.data, "created_at": row.created_at}
        for row in session.scalars(
            select(InvestigationTrace)
            .where(InvestigationTrace.organization_id == org, InvestigationTrace.run_id == run_id)
            .order_by(InvestigationTrace.created_at, InvestigationTrace.id)
            .offset(offset)
            .limit(limit)
        )
    ]
