"""Opt-in whole-application role boundary; legacy tokens cannot bypass demo roles."""

import hashlib

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.concurrency import run_in_threadpool

from clearledger.case_domain import CaseError
from clearledger.review_identity import reviewer

PUBLIC = {"/health", "/ready", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
REVIEW_SUFFIXES = {
    "/review-actions",
    "/draft-evidence-request",
    "/request-evidence",
    "/record-response",
    "/review-comments",
    "/close",
    "/reopen",
}


def read_operation(request):
    return request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path.endswith(
        ("/evidence/search", "/evidence/verify")
    )


def delegated(path):
    return (
        path.startswith(("/review/", "/finance/", "/journal-proposals/"))
        or path.endswith(tuple(REVIEW_SUFFIXES))
        or path.endswith(("/finance-source-reviews", "/journal-proposals"))
    )


async def enforce(request, call_next):
    settings = request.app.state.settings
    if (
        not (settings.review_access_enabled or settings.review_demo_enabled)
        or request.url.path in PUBLIC
        or delegated(request.url.path)
    ):
        return await call_next(request)

    def admission():
        with request.app.state.session_factory() as session:
            identity = reviewer(request, session)
            identity.require("READ" if read_operation(request) else "WORK")
            return identity

    try:
        identity = await run_in_threadpool(admission)
    except DBAPIError:
        return JSONResponse(
            {"detail": "REVIEW_DATABASE_OR_QUERY_LIMIT"},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    except (CaseError, HTTPException) as error:
        return JSONResponse(
            {"detail": error.code if isinstance(error, CaseError) else str(error.detail)},
            status_code=error.status if isinstance(error, CaseError) else error.status_code,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    request.state.review_reviewer = identity
    request.state.review_readonly = read_operation(request)
    # Existing ingestion/event APIs receive canonical actor provenance, never an
    # attacker-supplied label. No authorization credential is rewritten or minted.
    actor = "review." + hashlib.sha256(identity.identity.encode()).hexdigest()
    request.scope["headers"] = [
        (k, v) for k, v in request.scope["headers"] if k.lower() != b"x-actor-id"
    ] + [(b"x-actor-id", actor.encode())]
    if hasattr(request, "_headers"):
        del request._headers
    return await call_next(request)
