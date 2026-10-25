"""Authenticated role-checked review APIs. No mail transport or financial mutation tool."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from clearledger.api import DB, company_scope
from clearledger.case_api import Limit, Offset
from clearledger.case_domain import CaseError
from clearledger.case_models import Case, Claim
from clearledger.case_repository import members, root, scoped
from clearledger.case_schemas import CaseView, ClaimView
from clearledger.case_service import claim_view
from clearledger.case_service import view as case_view
from clearledger.document_runtime import LocalOriginals
from clearledger.evidence_api import EvidenceRoute
from clearledger.matching_api import Key
from clearledger.review_contract import (
    ActionView,
    DraftInput,
    EvidenceRequest,
    Login,
    LoginResult,
    Note,
    ResponseInput,
)
from clearledger.review_identity import ReviewIdentity, demo_session, local_enabled, login
from clearledger.review_models import (
    DemoAuthEvent,
    DemoRevocation,
    DemoUser,
    ReviewAction,
    ReviewAudit,
)
from clearledger.review_service import action_view, command

router = APIRouter(tags=["review-and-recovery"], route_class=EvidenceRoute)


@router.post("/review/demo/login", response_model=LoginResult)
def sign_in(body: Login, session: DB, request: Request, response: Response):
    local_enabled(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return login(session, company_scope(request, session), body)


@router.post("/review/demo/logout")
def sign_out(session: DB, identity: ReviewIdentity, request: Request):
    from clearledger.case_domain import CaseError

    if identity.trusted:
        raise CaseError("DEMO_SESSION_REQUIRED", 401)
    _, row = demo_session(request, session, identity.organization_id)
    if scoped(session, DemoRevocation, identity.organization_id, session_id=row.id) is None:
        session.add(DemoRevocation(organization_id=identity.organization_id, session_id=row.id))
        session.add(
            DemoAuthEvent(
                organization_id=identity.organization_id,
                kind="LOGOUT",
                data={"user_id": str(identity.subject)},
            )
        )
    session.commit()
    return {"revoked": True, "authority": "LOCAL_DEMO_ONLY"}


@router.get("/review/me")
def me(identity: ReviewIdentity):
    return {
        "subject": identity.subject,
        "role": identity.role,
        "authority": "VERIFIED" if identity.trusted else "LOCAL_DEMO_ONLY",
        "financial_authority": False,
    }


@router.get("/review/demo/users")
def users(session: DB, identity: ReviewIdentity, limit: Limit = 100, offset: Offset = 0):
    identity.require("READ")
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "enabled": u.enabled,
            "version": u.version,
            "authority": "LOCAL_DEMO_ONLY",
        }
        for u in session.scalars(
            select(DemoUser)
            .where(DemoUser.organization_id == identity.organization_id)
            .order_by(DemoUser.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/cases/{case_id}/review-actions", response_model=list[ActionView])
def actions(
    case_id: UUID,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
    limit: Limit = 100,
    offset: Offset = 0,
):
    org = identity.organization_id
    ids = members(session, org, root(session, org, case_id))
    return [
        action_view(session, org, a, request.app.state.settings)
        for a in session.scalars(
            select(ReviewAction)
            .where(ReviewAction.organization_id == org, ReviewAction.case_id.in_(ids))
            .order_by(ReviewAction.created_at, ReviewAction.id)
            .offset(offset)
            .limit(limit)
        )
    ]


def execute(case_id, operation, body, key, session, identity, request):
    try:
        action = command(
            session,
            identity.organization_id,
            case_id,
            operation,
            body,
            key,
            identity,
            request.app.state.settings,
            request.app.state.finance_identity_verifier,
        )
    except (CaseError, HTTPException) as error:
        session.rollback()
        session.add(
            ReviewAudit(
                organization_id=identity.organization_id,
                actor=identity.provenance,
                operation=operation,
                outcome="DENIED",
                code=error.code if isinstance(error, CaseError) else "REVIEW_AUTHORIZATION_DENIED",
                target_id=case_id,
            )
        )
        session.commit()
        raise
    return action_view(session, identity.organization_id, action, request.app.state.settings)


@router.get("/review/cases", response_model=list[CaseView])
def case_list(
    session: DB, identity: ReviewIdentity, request: Request, limit: Limit = 100, offset: Offset = 0
):
    return [
        case_view(
            session,
            identity.organization_id,
            c,
            LocalOriginals(request.app.state.settings.document_root),
        )
        for c in session.scalars(
            select(Case)
            .where(Case.organization_id == identity.organization_id, Case.merged_into_id.is_(None))
            .order_by(Case.created_at, Case.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/review/cases/{case_id}", response_model=CaseView)
def case_get(case_id: UUID, session: DB, identity: ReviewIdentity, request: Request):
    return case_view(
        session,
        identity.organization_id,
        root(session, identity.organization_id, case_id),
        LocalOriginals(request.app.state.settings.document_root),
        case_id,
    )


@router.get("/review/cases/{case_id}/claims", response_model=list[ClaimView])
def claim_list(
    case_id: UUID,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
    limit: Limit = 100,
    offset: Offset = 0,
):
    org = identity.organization_id
    ids = members(session, org, root(session, org, case_id))
    return [
        claim_view(session, org, c, LocalOriginals(request.app.state.settings.document_root))
        for c in session.scalars(
            select(Claim)
            .where(Claim.organization_id == org, Claim.case_id.in_(ids))
            .order_by(Claim.created_at, Claim.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/review/audit")
def audit_history(session: DB, identity: ReviewIdentity, limit: Limit = 100, offset: Offset = 0):
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "operation": a.operation,
            "outcome": a.outcome,
            "code": a.code,
            "target_id": a.target_id,
            "created_at": a.created_at,
        }
        for a in session.scalars(
            select(ReviewAudit)
            .where(ReviewAudit.organization_id == identity.organization_id)
            .order_by(ReviewAudit.created_at, ReviewAudit.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.post("/cases/{case_id}/draft-evidence-request", response_model=ActionView)
def draft(
    case_id: UUID,
    body: DraftInput,
    key: Key,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
):
    return execute(case_id, "DRAFT", body, key, session, identity, request)


@router.post("/cases/{case_id}/request-evidence", response_model=ActionView)
def request_evidence(
    case_id: UUID,
    body: EvidenceRequest,
    key: Key,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
):
    return execute(case_id, "REQUEST_EVIDENCE", body, key, session, identity, request)


@router.post("/cases/{case_id}/record-response", response_model=ActionView)
def response(
    case_id: UUID,
    body: ResponseInput,
    key: Key,
    session: DB,
    identity: ReviewIdentity,
    request: Request,
):
    return execute(case_id, "RESPONSE", body, key, session, identity, request)


@router.post("/cases/{case_id}/review-comments", response_model=ActionView)
def comment(
    case_id: UUID, body: Note, key: Key, session: DB, identity: ReviewIdentity, request: Request
):
    return execute(case_id, "COMMENT", body, key, session, identity, request)


@router.post("/cases/{case_id}/close", response_model=ActionView)
def close(
    case_id: UUID, body: Note, key: Key, session: DB, identity: ReviewIdentity, request: Request
):
    return execute(case_id, "CLOSE", body, key, session, identity, request)


@router.post("/cases/{case_id}/reopen", response_model=ActionView)
def reopen(
    case_id: UUID, body: Note, key: Key, session: DB, identity: ReviewIdentity, request: Request
):
    return execute(case_id, "REOPEN", body, key, session, identity, request)
