"""Immutable tasks and decisions with scoped source foreign keys."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_models import fk
from clearledger.models import Base, ScopedRecord, scope_constraints


class CorrelationTask(ScopedRecord, Base):
    __tablename__ = "correlation_tasks"
    __table_args__ = (
        *scope_constraints("correlation_tasks"),
        fk("correlation_tasks", "case_id", "cases"),
        fk("correlation_tasks", "document_id", "documents"),
        fk("correlation_tasks", "extraction_id", "document_extractions"),
        ForeignKeyConstraint(
            ["organization_id", "extraction_id", "document_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.id",
                "document_extractions.document_id",
            ],
            name="fk_correlation_extraction_document",
        ),
        UniqueConstraint(
            "organization_id", "document_id", "input_sha256", name="uq_correlation_basis"
        ),
    )
    case_id: Mapped[UUID]
    document_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    input_sha256: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(100))
    snapshot: Mapped[dict] = mapped_column(JSONB)


class CorrelationDecision(ScopedRecord, Base):
    __tablename__ = "correlation_decisions"
    __table_args__ = (
        *scope_constraints("correlation_decisions"),
        fk("correlation_decisions", "task_id", "correlation_tasks"),
        fk("correlation_decisions", "receipt_id", "receipts"),
        fk("correlation_decisions", "invoice_id", "invoices"),
        fk("correlation_decisions", "association_id", "document_associations"),
        UniqueConstraint("organization_id", "task_id", name="uq_correlation_decision"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_correlation_key"),
        CheckConstraint("decision IN ('CONFIRM','REJECT')", name="ck_correlation_decision"),
        CheckConstraint(
            "(decision='CONFIRM' AND receipt_id IS NOT NULL AND invoice_id IS NOT NULL "
            "AND association_id IS NOT NULL) OR (decision='REJECT' AND receipt_id IS NULL "
            "AND invoice_id IS NULL AND association_id IS NULL)",
            name="ck_correlation_targets",
        ),
    )
    task_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(8))
    actor: Mapped[dict] = mapped_column(JSONB)
    receipt_id: Mapped[UUID | None]
    invoice_id: Mapped[UUID | None]
    association_id: Mapped[UUID | None]
