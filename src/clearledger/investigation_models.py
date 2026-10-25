"""Durable workflow metadata. No allocations, approvals or journals."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_models import fk
from clearledger.models import Base, ScopedRecord, scope_constraints


class Investigation(ScopedRecord, Base):
    __tablename__ = "investigations"
    __table_args__ = (
        *scope_constraints("investigations"),
        fk("investigations", "case_id", "cases"),
        UniqueConstraint("organization_id", "input_sha256", name="uq_investigation_input"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "source_case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_investigation_source_version",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "result_case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_investigation_result_version",
        ),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','AWAITING_REVIEW','STALE')",
            name="ck_investigation_status",
        ),
        CheckConstraint(
            "tool_calls>=0 AND provider_attempts>=0 AND reserved_input_tokens>=0 AND "
            "reserved_output_tokens>=0 AND reserved_cost_paise>=0",
            name="ck_investigation_usage",
        ),
    )
    case_id: Mapped[UUID]
    source_case_version: Mapped[int] = mapped_column(Integer)
    result_case_version: Mapped[int | None] = mapped_column(Integer)
    input_sha256: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="QUEUED")
    recommendation: Mapped[str] = mapped_column(String(24), default="AWAITING_REVIEW")
    snapshot: Mapped[dict] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    provider_attempts: Mapped[int] = mapped_column(Integer, default=0)
    reserved_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_cost_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))


class InvestigationRequest(ScopedRecord, Base):
    __tablename__ = "investigation_requests"
    __table_args__ = (
        *scope_constraints("investigation_requests"),
        fk("investigation_requests", "run_id", "investigations"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_investigation_request"),
    )
    run_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(100))


class InvestigationCheckpoint(ScopedRecord, Base):
    __tablename__ = "investigation_checkpoints"
    __table_args__ = (
        *scope_constraints("investigation_checkpoints"),
        fk("investigation_checkpoints", "run_id", "investigations"),
        UniqueConstraint(
            "organization_id", "run_id", "checkpoint_id", name="uq_investigation_checkpoint"
        ),
    )
    run_id: Mapped[UUID]
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[str | None] = mapped_column(String(100))
    checkpoint: Mapped[dict] = mapped_column(JSONB)
    meta: Mapped[dict] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))


class InvestigationWrite(ScopedRecord, Base):
    __tablename__ = "investigation_writes"
    __table_args__ = (
        *scope_constraints("investigation_writes"),
        fk("investigation_writes", "run_id", "investigations"),
        UniqueConstraint(
            "organization_id",
            "run_id",
            "checkpoint_id",
            "task_id",
            "write_index",
            name="uq_investigation_write",
        ),
    )
    run_id: Mapped[UUID]
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    task_id: Mapped[str] = mapped_column(String(100))
    task_path: Mapped[str] = mapped_column(String(500))
    write_index: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict] = mapped_column(JSONB)


class InvestigationOperation(ScopedRecord, Base):
    __tablename__ = "investigation_operations"
    __table_args__ = (
        *scope_constraints("investigation_operations"),
        fk("investigation_operations", "run_id", "investigations"),
        UniqueConstraint(
            "organization_id", "run_id", "operation_key", name="uq_investigation_operation"
        ),
    )
    run_id: Mapped[UUID]
    operation_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_paise: Mapped[int] = mapped_column(BigInteger, default=0)


class InvestigationResult(ScopedRecord, Base):
    __tablename__ = "investigation_results"
    __table_args__ = (
        *scope_constraints("investigation_results"),
        fk("investigation_results", "run_id", "investigations"),
        ForeignKeyConstraint(
            ["organization_id", "run_id", "operation_key"],
            [
                "investigation_operations.organization_id",
                "investigation_operations.run_id",
                "investigation_operations.operation_key",
            ],
            name="fk_investigation_result_operation",
        ),
        UniqueConstraint(
            "organization_id", "run_id", "operation_key", name="uq_investigation_result"
        ),
    )
    run_id: Mapped[UUID]
    operation_key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict] = mapped_column(JSONB)


class InvestigationFinding(ScopedRecord, Base):
    __tablename__ = "investigation_findings"
    __table_args__ = (
        *scope_constraints("investigation_findings"),
        fk("investigation_findings", "run_id", "investigations"),
        fk("investigation_findings", "claim_id", "claims"),
        fk("investigation_findings", "case_id", "cases"),
        UniqueConstraint("organization_id", "run_id", "claim_id", name="uq_investigation_claim"),
    )
    run_id: Mapped[UUID]
    case_id: Mapped[UUID]
    claim_id: Mapped[UUID]
    basis_sha256: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict] = mapped_column(JSONB)


class InvestigationInvalidation(ScopedRecord, Base):
    __tablename__ = "investigation_invalidations"
    __table_args__ = (
        *scope_constraints("investigation_invalidations"),
        fk("investigation_invalidations", "finding_id", "investigation_findings"),
        fk("investigation_invalidations", "event_id", "domain_events"),
        UniqueConstraint(
            "organization_id", "finding_id", "event_id", name="uq_investigation_invalidation"
        ),
    )
    finding_id: Mapped[UUID]
    event_id: Mapped[UUID]


class InvestigationTrace(ScopedRecord, Base):
    __tablename__ = "investigation_traces"
    __table_args__ = (
        *scope_constraints("investigation_traces"),
        fk("investigation_traces", "run_id", "investigations"),
        UniqueConstraint("organization_id", "run_id", "trace_key", name="uq_investigation_trace"),
    )
    run_id: Mapped[UUID]
    trace_key: Mapped[str] = mapped_column(String(64))
    node: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSONB)
