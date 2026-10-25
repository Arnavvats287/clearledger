"""Immutable source manifests and ingestion provenance; no financial state."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_models import fk
from clearledger.models import Base, ScopedRecord, scope_constraints


class EvidenceRecord(ScopedRecord, Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        *scope_constraints("evidence_records"),
        fk("evidence_records", "customer_id", "customers"),
        fk("evidence_records", "document_id", "documents"),
        fk("evidence_records", "previous_id", "evidence_records"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "customer_id"],
            ["invoices.organization_id", "invoices.id", "invoices.customer_id"],
            name="fk_evidence_invoice_owner",
        ),
        UniqueConstraint(
            "organization_id",
            "source_system",
            "source_record_id",
            "revision",
            name="uq_evidence_source_revision",
        ),
        UniqueConstraint("organization_id", "previous_id", name="uq_evidence_successor"),
        CheckConstraint(
            "revision > 0 AND ((revision = 1) = (previous_id IS NULL))", name="ck_evidence_revision"
        ),
        CheckConstraint("effective_to >= effective_from", name="ck_evidence_dates"),
        CheckConstraint(
            "kind IN ('CONTRACT','PROMOTION','WMS','POD','TAX','INVOICE','REMITTANCE')",
            name="ck_evidence_kind",
        ),
        CheckConstraint("length(excerpt) BETWEEN 1 AND 2000", name="ck_evidence_excerpt"),
        Index("ix_evidence_scope", "organization_id", "customer_id", "kind", "invoice_id"),
        Index("ix_evidence_search", "search_vector", postgresql_using="gin"),
    )
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer)
    previous_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(String(20))
    customer_id: Mapped[UUID]
    invoice_id: Mapped[UUID | None]
    document_id: Mapped[UUID]
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSONB)
    excerpt: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', excerpt)", persisted=True)
    )


class EvidenceRequest(ScopedRecord, Base):
    __tablename__ = "evidence_requests"
    __table_args__ = (
        *scope_constraints("evidence_requests"),
        fk("evidence_requests", "record_id", "evidence_records"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_evidence_request_key"),
    )
    record_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(100))


class EvidenceEvent(ScopedRecord, Base):
    __tablename__ = "evidence_events"
    __table_args__ = (
        *scope_constraints("evidence_events"),
        fk("evidence_events", "record_id", "evidence_records"),
        fk("evidence_events", "request_id", "evidence_requests"),
        UniqueConstraint("organization_id", "request_id", name="uq_evidence_request_event"),
        CheckConstraint(
            "event_type IN ('evidence.registered','evidence.replayed')",
            name="ck_evidence_event_kind",
        ),
    )
    record_id: Mapped[UUID]
    request_id: Mapped[UUID]
    actor_id: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(32))
