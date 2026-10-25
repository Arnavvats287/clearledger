"""Authenticated nonfinancial case boundary; asserted actor labels grant no authority."""

import hashlib
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from clearledger.api import DB, company_scope
from clearledger.case_domain import CaseError, CaseState, ClaimState
from clearledger.case_models import (
    Case,
    CaseInvalidation,
    CaseProposal,
    CaseReceipt,
    CaseVersion,
    Claim,
    ClaimVersion,
    DomainEvent,
    EvidenceLink,
    Hypothesis,
    OutboxEvent,
    Reevaluation,
)
from clearledger.case_repository import members, root
from clearledger.case_schemas import (
    AttachInput,
    BindingView,
    BindInput,
    CaseView,
    ClaimHistoryView,
    ClaimTransitionInput,
    ClaimView,
    EvidenceView,
    HistoryView,
    HypothesisView,
    ReconcileInput,
    ReconcileView,
    ReevaluationView,
    TransitionInput,
    VersionInput,
    WorkView,
)
from clearledger.case_service import claim_view, command, reconcile, view
from clearledger.case_sources import claim_basis, current_context, proposal_current
from clearledger.document_contract import ExtractionError
from clearledger.document_runtime import LocalOriginals
from clearledger.matching import owned
from clearledger.matching_api import Actor, Key
from clearledger.models import MatchingProposal


class SafeCaseRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                raise HTTPException(
                    422,
                    [
                        {"loc": item["loc"], "type": item["type"], "msg": "Invalid case request"}
                        for item in error.errors()
                    ],
                ) from None
            except CaseError as error:
                raise HTTPException(error.status, error.code) from None
            except ExtractionError:
                raise HTTPException(422, "INVALID_CASE_SOURCE_EVIDENCE") from None

        return safe


router = APIRouter(tags=["cases"], route_class=SafeCaseRoute)


def scoped_access(request, session):
    org = company_scope(request, session)
    if request.method == "GET":
        key = int.from_bytes(hashlib.sha256(org.bytes).digest()[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": key})
    return org


def access(
    request: Request, session: DB, authorization: Annotated[str | None, Header()] = None
) -> UUID:
    settings = request.app.state.settings
    write = settings.document_api_token.get_secret_value() if settings.document_api_token else ""
    read = settings.case_read_token.get_secret_value() if settings.case_read_token else ""
    supplied = (
        authorization.removeprefix("Bearer ")
        if authorization and authorization.startswith("Bearer ")
        else ""
    )
    if len(write) < 32:
        raise HTTPException(503, "Configure strong DOCUMENT_API_TOKEN for local case access")
    if read and secrets.compare_digest(read.encode(), write.encode()):
        raise HTTPException(503, "Case read and write credentials must differ")
    if secrets.compare_digest(supplied.encode(), write.encode()):
        return scoped_access(request, session)
    if len(read) >= 32 and secrets.compare_digest(supplied.encode(), read.encode()):
        if request.method != "GET":
            raise HTTPException(403, "Read-only case credential")
        return scoped_access(request, session)
    raise HTTPException(401, "Case authentication required", headers={"WWW-Authenticate": "Bearer"})


Scope = Annotated[UUID, Depends(access)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def store(request):
    return LocalOriginals(request.app.state.settings.document_root)


@router.get("/cases", response_model=list[CaseView])
def case_list(
    session: DB,
    org: Scope,
    request: Request,
    limit: Limit = 100,
    offset: Offset = 0,
    state: CaseState | None = None,
    customer_id: UUID | None = None,
    receipt_id: UUID | None = None,
):
    statement = select(Case).where(Case.organization_id == org, Case.merged_into_id.is_(None))
    if state is not None:
        statement = statement.where(Case.state == state)
    if customer_id is not None:
        statement = statement.where(Case.customer_id == customer_id)
    if receipt_id is not None:
        link = session.scalar(
            select(CaseReceipt).where(
                CaseReceipt.organization_id == org, CaseReceipt.receipt_id == receipt_id
            )
        )
        statement = (
            statement.where(Case.id == root(session, org, link.case_id).id)
            if link
            else statement.where(False)
        )
    rows = session.scalars(statement.order_by(Case.created_at, Case.id).offset(offset).limit(limit))
    return [view(session, org, row, store(request)) for row in rows]


@router.get("/cases/{case_id}", response_model=CaseView)
def case_get(case_id: UUID, session: DB, org: Scope, request: Request):
    return view(session, org, owned(session, Case, org, case_id), store(request), case_id)


@router.get("/cases/{case_id}/claims", response_model=list[ClaimView])
def claims(
    case_id: UUID,
    session: DB,
    org: Scope,
    request: Request,
    limit: Limit = 100,
    offset: Offset = 0,
    state: ClaimState | None = None,
):
    case = root(session, org, case_id)
    statement = select(Claim).where(
        Claim.organization_id == org, Claim.case_id.in_(members(session, org, case))
    )
    if state is not None:
        statement = statement.where(Claim.state == state)
    return [
        claim_view(session, org, c, store(request))
        for c in session.scalars(
            statement.order_by(Claim.created_at, Claim.id).offset(offset).limit(limit)
        )
    ]


@router.get("/claims/{claim_id}", response_model=ClaimView)
def claim_get(claim_id: UUID, session: DB, org: Scope, request: Request):
    return claim_view(session, org, owned(session, Claim, org, claim_id), store(request))


@router.get("/claims/{claim_id}/versions", response_model=list[ClaimHistoryView])
def claim_versions(claim_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    owned(session, Claim, org, claim_id)
    return session.scalars(
        select(ClaimVersion)
        .where(ClaimVersion.organization_id == org, ClaimVersion.claim_id == claim_id)
        .order_by(ClaimVersion.claim_version)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/cases/{case_id}/reevaluations", response_model=list[ReevaluationView])
def reevaluations(case_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    case = root(session, org, case_id)
    return session.scalars(
        select(Reevaluation)
        .where(
            Reevaluation.organization_id == org,
            Reevaluation.case_id.in_(members(session, org, case)),
        )
        .order_by(Reevaluation.created_at, Reevaluation.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/cases/{case_id}/events", response_model=list[HistoryView])
def events(case_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    case = root(session, org, case_id)
    return session.scalars(
        select(DomainEvent)
        .where(
            DomainEvent.organization_id == org, DomainEvent.case_id.in_(members(session, org, case))
        )
        .order_by(DomainEvent.created_at, DomainEvent.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/cases/{case_id}/versions", response_model=list[HistoryView])
def versions(case_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    owned(session, Case, org, case_id)
    return session.scalars(
        select(CaseVersion)
        .where(CaseVersion.organization_id == org, CaseVersion.case_id == case_id)
        .order_by(CaseVersion.case_version)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceView])
def evidence(case_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    case = root(session, org, case_id)
    return session.scalars(
        select(EvidenceLink)
        .where(
            EvidenceLink.organization_id == org,
            EvidenceLink.case_id.in_(members(session, org, case)),
        )
        .order_by(EvidenceLink.created_at, EvidenceLink.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/claims/{claim_id}/evidence", response_model=list[EvidenceView])
def claim_evidence(claim_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    owned(session, Claim, org, claim_id)
    return session.scalars(
        select(EvidenceLink)
        .where(EvidenceLink.organization_id == org, EvidenceLink.claim_id == claim_id)
        .order_by(EvidenceLink.created_at, EvidenceLink.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/cases/{case_id}/hypotheses", response_model=list[HypothesisView])
def hypotheses(
    case_id: UUID, session: DB, org: Scope, request: Request, limit: Limit = 100, offset: Offset = 0
):
    case = root(session, org, case_id)
    rows = session.scalars(
        select(Hypothesis)
        .where(
            Hypothesis.organization_id == org, Hypothesis.case_id.in_(members(session, org, case))
        )
        .order_by(Hypothesis.created_at, Hypothesis.id)
        .offset(offset)
        .limit(limit)
    ).all()
    invalid = set(
        session.scalars(
            select(CaseInvalidation.hypothesis_id).where(
                CaseInvalidation.organization_id == org,
                CaseInvalidation.hypothesis_id.in_([h.id for h in rows]),
            )
        )
    )
    context = current_context(session, org, case, store(request)) if rows else None
    return [
        HypothesisView(
            id=h.id,
            claim_id=h.claim_id,
            basis_case_id=h.basis_case_id,
            basis_case_version=h.basis_case_version,
            content=h.content,
            is_stale=h.id in invalid
            or h.basis_sha256
            != claim_basis(
                session,
                org,
                case,
                owned(session, Claim, org, h.claim_id),
                store(request),
                context=context,
            ),
        )
        for h in rows
    ]


@router.get("/cases/{case_id}/matching-proposals", response_model=list[BindingView])
def bindings(
    case_id: UUID, session: DB, org: Scope, request: Request, limit: Limit = 100, offset: Offset = 0
):
    case = root(session, org, case_id)
    rows = session.scalars(
        select(CaseProposal)
        .where(
            CaseProposal.organization_id == org,
            CaseProposal.case_id.in_(members(session, org, case)),
        )
        .order_by(CaseProposal.created_at, CaseProposal.id)
        .offset(offset)
        .limit(limit)
    ).all()
    invalid = set(
        session.scalars(
            select(CaseInvalidation.case_proposal_id).where(
                CaseInvalidation.organization_id == org,
                CaseInvalidation.case_proposal_id.in_([p.id for p in rows]),
            )
        )
    )
    return [
        BindingView(
            id=p.id,
            matching_proposal_id=p.matching_proposal_id,
            basis_case_version=p.basis_case_version,
            is_stale=view(session, org, case, store(request)).is_stale
            or p.id in invalid
            or not proposal_current(
                session,
                org,
                owned(session, MatchingProposal, org, p.matching_proposal_id),
                request.app.state.settings,
            ),
        )
        for p in rows
    ]


@router.get("/cases/{case_id}/work", response_model=list[WorkView])
def work(case_id: UUID, session: DB, org: Scope, limit: Limit = 100, offset: Offset = 0):
    case = root(session, org, case_id)
    rows = session.execute(
        select(OutboxEvent, DomainEvent)
        .join(
            DomainEvent,
            (OutboxEvent.event_id == DomainEvent.id)
            & (OutboxEvent.organization_id == DomainEvent.organization_id),
        )
        .where(
            OutboxEvent.organization_id == org, DomainEvent.case_id.in_(members(session, org, case))
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        WorkView(
            id=o.id,
            event_id=e.id,
            event_type=e.event_type,
            status=o.status,
            attempts=o.attempts,
            available_at=o.available_at,
            last_error_code=o.last_error_code,
        )
        for o, e in rows
    ]


def run_command(operation, case_id, body, session, org, request, actor, key, claim_id=None):
    return command(
        session,
        org,
        case_id,
        key,
        actor,
        operation,
        body,
        request.app.state.settings,
        store(request),
        claim_id,
    )


@router.post("/cases/reconcile", response_model=ReconcileView)
def reconcile_sources(body: ReconcileInput, session: DB, org: Scope, actor: Actor):
    return reconcile(session, org, actor, body)


@router.post("/cases/{case_id}/transition", response_model=CaseView)
def transition(
    case_id: UUID,
    body: TransitionInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command("transition", case_id, body, session, org, request, actor, key)


@router.post("/cases/{case_id}/investigate", response_model=CaseView)
def investigate(
    case_id: UUID,
    body: VersionInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command("investigate", case_id, body, session, org, request, actor, key)


@router.post("/cases/{case_id}/refresh", response_model=CaseView)
def refresh(
    case_id: UUID,
    body: VersionInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command("refresh", case_id, body, session, org, request, actor, key)


@router.post("/cases/{case_id}/attach-evidence", response_model=CaseView)
def attach_evidence(
    case_id: UUID,
    body: AttachInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command("attach", case_id, body, session, org, request, actor, key)


@router.post("/cases/{case_id}/matching-proposals", response_model=CaseView)
def bind_proposal(
    case_id: UUID,
    body: BindInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command("bind", case_id, body, session, org, request, actor, key)


@router.post("/cases/{case_id}/claims/{claim_id}/transition", response_model=CaseView)
def transition_claim(
    case_id: UUID,
    claim_id: UUID,
    body: ClaimTransitionInput,
    session: DB,
    org: Scope,
    request: Request,
    actor: Actor,
    key: Key,
):
    return run_command(
        "claim_transition", case_id, body, session, org, request, actor, key, claim_id
    )
