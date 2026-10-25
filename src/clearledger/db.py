from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def build_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
    )


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        reviewer = getattr(request.state, "review_reviewer", None)
        if reviewer is not None:
            session.info["review_verifier"] = request.app.state.finance_identity_verifier
        if reviewer is not None and not request.state.review_readonly:
            from sqlalchemy import text

            from clearledger.matching import lock_company
            from clearledger.review_models import ReviewAudit
            from clearledger.review_service import current_reviewer

            session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
            session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
            lock_company(session, reviewer.organization_id)
            session.info["review_verifier"] = request.app.state.finance_identity_verifier
            current_reviewer(session, reviewer.organization_id, reviewer, "WORK")
            reviewer.require("WORK")
            session.add(
                ReviewAudit(
                    organization_id=reviewer.organization_id,
                    actor=reviewer.provenance,
                    operation="LEGACY_WRITE",
                    outcome="ADMITTED",
                    code="ROLE_VERIFIED",
                    target_id=reviewer.organization_id,
                )
            )
        yield session
