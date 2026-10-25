"""Distinct local demo sessions and trusted review identity; no finance adapter installation."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select, text

from clearledger.api import DB, company_scope
from clearledger.case_domain import CaseError
from clearledger.case_repository import scoped
from clearledger.finance_identity import Principal, authenticated
from clearledger.matching import lock_company
from clearledger.review_contract import Login, LoginResult, Role
from clearledger.review_models import DemoAuthEvent, DemoRevocation, DemoSession, DemoUser
from clearledger.review_password import verify


@dataclass(frozen=True)
class Reviewer:
    subject: UUID
    organization_id: UUID
    role: Role
    identity: str
    provenance: dict[str, Any]
    trusted: Principal | None = None

    def require(self, operation: str) -> None:
        if operation != "READ" and self.role == "AUDITOR":
            raise CaseError("REVIEW_READ_ONLY", 403)
        if operation in {"CONTROL", "CLOSE"} and self.role != "CONTROLLER":
            raise CaseError("REVIEW_CONTROLLER_REQUIRED", 403)
        if operation == "CLOSE":
            if self.trusted is None:
                raise CaseError("VERIFIED_CLOSURE_AUTHORITY_REQUIRED", 503)
            self.trusted.require("APPROVE", self.organization_id)


def local_enabled(request: Request) -> None:
    # No forwarded-address trust. TestClient is permitted only for isolated ASGI tests.
    if (
        not request.app.state.settings.review_demo_enabled
        or request.client is None
        or request.client.host not in {"127.0.0.1", "::1", "testclient"}
    ):
        raise HTTPException(403, "LOCAL_DEMO_ACCESS_DISABLED")


def login(session, org, body: Login) -> LoginResult:
    session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
    session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
    lock_company(session, org)
    now = datetime.now(UTC)
    count = session.scalar(
        select(func.count())
        .select_from(DemoAuthEvent)
        .where(
            DemoAuthEvent.organization_id == org,
            DemoAuthEvent.kind == "LOGIN_ATTEMPT",
            DemoAuthEvent.created_at >= now - timedelta(minutes=1),
        )
    )
    if count >= 20:
        raise CaseError("DEMO_LOGIN_RATE_LIMIT", 429)
    session.add(DemoAuthEvent(organization_id=org, kind="LOGIN_ATTEMPT", data={}))
    user = scoped(session, DemoUser, org, username=body.username)
    # A fixed dummy hash makes unknown-user timing follow the same bounded work.
    encoded = (
        user.password_hash if user else ("pbkdf2-sha256$600000$" + "00" * 16 + "$" + "00" * 32)
    )
    valid = verify(body.password.get_secret_value(), encoded)
    if not valid or user is None or not user.enabled:
        session.add(DemoAuthEvent(organization_id=org, kind="LOGIN_DENIED", data={}))
        session.commit()
        raise CaseError("DEMO_LOGIN_FAILED", 401)
    token = secrets.token_urlsafe(48)
    expiry = now + timedelta(minutes=30)
    row = DemoSession(
        organization_id=org,
        user_id=user.id,
        user_version=user.version,
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=expiry,
    )
    session.add(row)
    session.add(
        DemoAuthEvent(
            organization_id=org,
            kind="LOGIN_SUCCEEDED",
            data={"user_id": str(user.id), "user_version": user.version},
        )
    )
    session.commit()
    return LoginResult(access_token=token, expires_at=expiry)


def demo_session(request, session, org):
    local_enabled(request)
    value = request.headers.get("authorization", "")
    if not value.startswith("ReviewDemo ") or not 40 <= len(value) <= 100:
        raise CaseError("DEMO_SESSION_REQUIRED", 401)
    row = scoped(
        session,
        DemoSession,
        org,
        token_sha256=hashlib.sha256(value.removeprefix("ReviewDemo ").encode()).hexdigest(),
    )
    if row is None or row.expires_at <= datetime.now(UTC):
        raise CaseError("DEMO_SESSION_INVALID", 401)
    user = scoped(session, DemoUser, org, id=row.user_id)
    if (
        user is None
        or not user.enabled
        or user.version != row.user_version
        or scoped(session, DemoRevocation, org, session_id=row.id)
    ):
        raise CaseError("DEMO_SESSION_INVALID", 401)
    return user, row


def reviewer(request: Request, session: DB) -> Reviewer:
    org = company_scope(request, session)
    # Release the initial configuration read before serialization; all grants are
    # rechecked under the company lock used by the ensuing command.
    session.rollback()
    session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
    session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
    lock_company(session, org)
    if request.headers.get("authorization", "").startswith("ReviewDemo "):
        user, row = demo_session(request, session, org)
        return Reviewer(
            user.id,
            org,
            user.role,
            "local-demo:" + str(user.id),
            {
                "authority": "LOCAL_DEMO_ONLY",
                "subject": str(user.id),
                "role": user.role,
                "user_version": user.version,
                "session_id": str(row.id),
                "financial_authority": False,
            },
        )
    principal = authenticated(request)
    from clearledger.finance_repository import check_identity

    principal = check_identity(
        request.app.state.finance_identity_verifier, principal.provenance(), "REVIEW_READ", org
    )
    principal.require("REVIEW_READ", org)
    role: Role = (
        "CONTROLLER"
        if "REVIEW_CONTROL" in principal.permissions
        else "AR_ANALYST"
        if "REVIEW_WORK" in principal.permissions
        else "AUDITOR"
    )
    if principal.service:
        raise CaseError("HUMAN_REVIEWER_REQUIRED", 403)
    return Reviewer(
        principal.subject,
        org,
        role,
        principal.identity,
        {"authority": "VERIFIED", **principal.provenance()},
        principal,
    )


ReviewIdentity = Annotated[Reviewer, Depends(reviewer)]
