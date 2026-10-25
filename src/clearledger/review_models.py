"""Scoped local demo credentials and append-only review/recovery history."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_models import fk
from clearledger.models import Base, ScopedRecord, scope_constraints


class DemoUser(ScopedRecord, Base):
    __tablename__ = "review_demo_users"
    __table_args__ = (
        *scope_constraints("review_demo_users"),
        UniqueConstraint("organization_id", "username", name="uq_review_demo_username"),
        CheckConstraint("role IN ('AR_ANALYST','CONTROLLER','AUDITOR')", name="ck_review_role"),
    )
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DemoSession(ScopedRecord, Base):
    __tablename__ = "review_demo_sessions"
    __table_args__ = (
        *scope_constraints("review_demo_sessions"),
        fk("review_demo_sessions", "user_id", "review_demo_users"),
        UniqueConstraint("organization_id", "token_sha256", name="uq_review_session_token"),
        CheckConstraint("user_version > 0", name="ck_review_session_user_version"),
    )
    user_id: Mapped[UUID]
    user_version: Mapped[int]
    token_sha256: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DemoRevocation(ScopedRecord, Base):
    __tablename__ = "review_demo_revocations"
    __table_args__ = (
        *scope_constraints("review_demo_revocations"),
        fk("review_demo_revocations", "session_id", "review_demo_sessions"),
        UniqueConstraint("organization_id", "session_id", name="uq_review_revocation"),
    )
    session_id: Mapped[UUID]


class DemoAuthEvent(ScopedRecord, Base):
    __tablename__ = "review_demo_auth_events"
    __table_args__ = (*scope_constraints("review_demo_auth_events"),)
    kind: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSONB)


class ReviewAction(ScopedRecord, Base):
    __tablename__ = "review_actions"
    __table_args__ = (
        *scope_constraints("review_actions"),
        fk("review_actions", "case_id", "cases"),
        fk("review_actions", "in_reply_to", "review_actions"),
        fk("review_actions", "proposal_id", "finance_proposals"),
        CheckConstraint(
            "kind IN ('DRAFT','RESPONSE','REQUEST_EVIDENCE','COMMENT','CLOSE','REOPEN')",
            name="ck_review_action_kind",
        ),
        CheckConstraint(
            "basis_case_version > 0 AND result_case_version >= basis_case_version",
            name="ck_review_action_versions",
        ),
    )
    case_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(String(24))
    basis_case_version: Mapped[int]
    result_case_version: Mapped[int]
    actor: Mapped[dict] = mapped_column(JSONB)
    content: Mapped[dict] = mapped_column(JSONB)
    source_sha256: Mapped[str] = mapped_column(String(64))
    in_reply_to: Mapped[UUID | None]
    proposal_id: Mapped[UUID | None]


class ReviewCommand(ScopedRecord, Base):
    __tablename__ = "review_commands"
    __table_args__ = (
        *scope_constraints("review_commands"),
        fk("review_commands", "action_id", "review_actions"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_review_command_key"),
    )
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    action_id: Mapped[UUID]


class ReviewAudit(ScopedRecord, Base):
    __tablename__ = "review_audit"
    __table_args__ = (*scope_constraints("review_audit"),)
    actor: Mapped[dict] = mapped_column(JSONB)
    operation: Mapped[str] = mapped_column(String(24))
    outcome: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[UUID]
