"""Scoped case aggregates, immutable assertions/history and durable delivery records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_domain import CaseState, ClaimState
from clearledger.models import Base, ScopedRecord, scope_constraints


def fk(table, column, target):
    return ForeignKeyConstraint(
        ["organization_id", column],
        [target + ".organization_id", target + ".id"],
        name=f"fk_{table}_{column}",
    )


def states(column, values, name):
    return CheckConstraint(
        column + " IN (" + ",".join("'" + v + "'" for v in values) + ")", name=name
    )


class Case(ScopedRecord, Base):
    __tablename__ = "cases"
    __table_args__ = (
        *scope_constraints("cases"),
        fk("cases", "merged_into_id", "cases"),
        fk("cases", "customer_id", "customers"),
        states("state", CaseState, "ck_case_state"),
        CheckConstraint(
            "merged_into_id IS NULL OR merged_into_id <> id", name="ck_case_merge_self"
        ),
        Index("ix_case_queue", "organization_id", "state", "created_at", "id"),
    )
    state: Mapped[str] = mapped_column(String(32), default="NEW")
    merged_into_id: Mapped[UUID | None]
    customer_id: Mapped[UUID | None]
    context_sha256: Mapped[str] = mapped_column(String(64), default="")
    attention_codes: Mapped[list] = mapped_column(JSONB, default=list)
    write_txid: Mapped[int] = mapped_column(BigInteger, server_default=func.txid_current())


class DomainEvent(ScopedRecord, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        *scope_constraints("domain_events"),
        UniqueConstraint("organization_id", "event_key", name="uq_domain_event_key"),
        fk("domain_events", "case_id", "cases"),
        fk("domain_events", "receipt_id", "receipts"),
        fk("domain_events", "document_event_id", "document_events"),
        fk("domain_events", "matching_proposal_id", "matching_proposals"),
        CheckConstraint(
            "num_nonnulls(case_id,receipt_id,document_event_id,matching_proposal_id) = 1",
            name="ck_event_one_source",
        ),
    )
    event_key: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(100))
    case_id: Mapped[UUID | None]
    case_version: Mapped[int | None]
    receipt_id: Mapped[UUID | None]
    document_event_id: Mapped[UUID | None]
    matching_proposal_id: Mapped[UUID | None]
    payload: Mapped[dict] = mapped_column(JSONB)


class CaseVersion(ScopedRecord, Base):
    __tablename__ = "case_versions"
    __table_args__ = (
        *scope_constraints("case_versions"),
        fk("case_versions", "case_id", "cases"),
        fk("case_versions", "event_id", "domain_events"),
        UniqueConstraint("organization_id", "case_id", "case_version", name="uq_case_revision"),
        CheckConstraint("case_version > 0", name="ck_case_revision_positive"),
    )
    case_id: Mapped[UUID]
    case_version: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[UUID]
    snapshot: Mapped[dict] = mapped_column(JSONB)


class CaseReceipt(ScopedRecord, Base):
    __tablename__ = "case_receipts"
    __table_args__ = (
        *scope_constraints("case_receipts"),
        fk("case_receipts", "case_id", "cases"),
        fk("case_receipts", "receipt_id", "receipts"),
        UniqueConstraint("organization_id", "receipt_id", name="uq_case_receipt"),
    )
    case_id: Mapped[UUID]
    receipt_id: Mapped[UUID]


class CaseDocument(ScopedRecord, Base):
    __tablename__ = "case_documents"
    __table_args__ = (
        *scope_constraints("case_documents"),
        fk("case_documents", "case_id", "cases"),
        fk("case_documents", "document_id", "documents"),
        UniqueConstraint("organization_id", "document_id", name="uq_case_document"),
    )
    case_id: Mapped[UUID]
    document_id: Mapped[UUID]


class CaseInvoice(ScopedRecord, Base):
    __tablename__ = "case_invoices"
    __table_args__ = (
        *scope_constraints("case_invoices"),
        fk("case_invoices", "case_id", "cases"),
        fk("case_invoices", "invoice_id", "invoices"),
        fk("case_invoices", "matching_proposal_id", "matching_proposals"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "invoice_id",
            "matching_proposal_id",
            name="uq_case_invoice_source",
        ),
    )
    case_id: Mapped[UUID]
    invoice_id: Mapped[UUID]
    matching_proposal_id: Mapped[UUID]


class Claim(ScopedRecord, Base):
    __tablename__ = "claims"
    __table_args__ = (
        *scope_constraints("claims"),
        fk("claims", "case_id", "cases"),
        fk("claims", "document_id", "documents"),
        UniqueConstraint(
            "organization_id", "document_id", "fingerprint", name="uq_claim_assertion"
        ),
        UniqueConstraint("organization_id", "id", "case_id", name="uq_claim_case"),
        states("state", ClaimState, "ck_claim_state"),
        CheckConstraint("amount_paise IS NULL OR amount_paise >= 0", name="ck_claim_amount"),
        states(
            "category",
            ["tax", "damage", "short_shipment", "rebate", "early_discount", "other", "unknown"],
            "ck_claim_category",
        ),
        Index("ix_claim_case_state", "organization_id", "case_id", "state"),
    )
    case_id: Mapped[UUID]
    document_id: Mapped[UUID]
    fingerprint: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    amount_paise: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(32), default="EXTRACTED")
    assertion: Mapped[dict] = mapped_column(JSONB)
    write_txid: Mapped[int] = mapped_column(BigInteger, server_default=func.txid_current())


class ClaimSource(ScopedRecord, Base):
    __tablename__ = "claim_sources"
    __table_args__ = (
        *scope_constraints("claim_sources"),
        fk("claim_sources", "claim_id", "claims"),
        fk("claim_sources", "extraction_id", "document_extractions"),
        UniqueConstraint(
            "organization_id", "extraction_id", "claim_index", name="uq_claim_source_index"
        ),
        CheckConstraint("claim_index BETWEEN 0 AND 99", name="ck_claim_index"),
    )
    claim_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    claim_index: Mapped[int] = mapped_column(Integer)


class ClaimVersion(ScopedRecord, Base):
    __tablename__ = "claim_versions"
    __table_args__ = (
        *scope_constraints("claim_versions"),
        fk("claim_versions", "claim_id", "claims"),
        fk("claim_versions", "event_id", "domain_events"),
        UniqueConstraint("organization_id", "claim_id", "claim_version", name="uq_claim_revision"),
    )
    claim_id: Mapped[UUID]
    claim_version: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[UUID]
    snapshot: Mapped[dict] = mapped_column(JSONB)


class EvidenceLink(ScopedRecord, Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        *scope_constraints("evidence_links"),
        fk("evidence_links", "case_id", "cases"),
        fk("evidence_links", "document_id", "documents"),
        ForeignKeyConstraint(
            ["organization_id", "claim_id", "case_id"],
            ["claims.organization_id", "claims.id", "claims.case_id"],
            name="fk_evidence_claim_case",
        ),
        UniqueConstraint("organization_id", "case_id", "evidence_key", name="uq_case_evidence"),
        states(
            "relation",
            ["SOURCE_ASSERTION", "CONTEXT", "SUPPORTS", "CONTRADICTS"],
            "ck_evidence_relation",
        ),
        CheckConstraint("document_version > 0", name="ck_evidence_document_version"),
    )
    case_id: Mapped[UUID]
    claim_id: Mapped[UUID | None]
    document_id: Mapped[UUID]
    document_version: Mapped[int] = mapped_column(Integer)
    raw_sha256: Mapped[str] = mapped_column(String(64))
    canonical_sha256: Mapped[str] = mapped_column(String(64))
    span: Mapped[dict] = mapped_column(JSONB)
    relation: Mapped[str] = mapped_column(String(32))
    evidence_key: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(100))


class Hypothesis(ScopedRecord, Base):
    __tablename__ = "hypotheses"
    __table_args__ = (
        *scope_constraints("hypotheses"),
        ForeignKeyConstraint(
            ["organization_id", "claim_id", "case_id"],
            ["claims.organization_id", "claims.id", "claims.case_id"],
            name="fk_hypothesis_claim_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "basis_case_id", "basis_case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_hypothesis_basis",
        ),
        UniqueConstraint(
            "organization_id",
            "claim_id",
            "basis_case_id",
            "basis_case_version",
            name="uq_hypothesis_basis",
        ),
        CheckConstraint(
            "content->'financial_authority' IS NOT DISTINCT FROM 'false'::jsonb AND "
            "content->>'finding' IS NOT DISTINCT FROM 'UNASSESSED' AND "
            "content->'requires_human_review' IS NOT DISTINCT FROM 'true'::jsonb",
            name="ck_hypothesis_placeholder",
        ),
    )
    case_id: Mapped[UUID]
    claim_id: Mapped[UUID]
    basis_case_id: Mapped[UUID]
    basis_case_version: Mapped[int] = mapped_column(Integer)
    basis_sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)


class CaseProposal(ScopedRecord, Base):
    __tablename__ = "case_proposals"
    __table_args__ = (
        *scope_constraints("case_proposals"),
        fk("case_proposals", "case_id", "cases"),
        fk("case_proposals", "matching_proposal_id", "matching_proposals"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "basis_case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_case_proposal_basis",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "matching_proposal_id",
            "basis_case_version",
            name="uq_case_proposal_basis",
        ),
    )
    case_id: Mapped[UUID]
    matching_proposal_id: Mapped[UUID]
    basis_case_version: Mapped[int] = mapped_column(Integer)


class CaseInvalidation(ScopedRecord, Base):
    __tablename__ = "case_invalidations"
    __table_args__ = (
        *scope_constraints("case_invalidations"),
        fk("case_invalidations", "case_id", "cases"),
        fk("case_invalidations", "hypothesis_id", "hypotheses"),
        fk("case_invalidations", "case_proposal_id", "case_proposals"),
        CheckConstraint(
            "num_nonnulls(hypothesis_id,case_proposal_id) = 1", name="ck_invalidation_target"
        ),
        UniqueConstraint("organization_id", "invalidation_key", name="uq_case_invalidation"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_invalidation_revision",
        ),
    )
    case_id: Mapped[UUID]
    case_version: Mapped[int] = mapped_column(Integer)
    hypothesis_id: Mapped[UUID | None]
    case_proposal_id: Mapped[UUID | None]
    reason: Mapped[str] = mapped_column(String(64))
    invalidation_key: Mapped[str] = mapped_column(String(64))


class Reevaluation(ScopedRecord, Base):
    __tablename__ = "case_reevaluations"
    __table_args__ = (
        *scope_constraints("case_reevaluations"),
        fk("case_reevaluations", "case_id", "cases"),
        fk("case_reevaluations", "event_id", "domain_events"),
        UniqueConstraint("organization_id", "event_id", name="uq_reevaluation_event"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "evaluated_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_reevaluation_revision",
        ),
    )
    case_id: Mapped[UUID]
    event_id: Mapped[UUID]
    scheduled_version: Mapped[int] = mapped_column(Integer)
    evaluated_version: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSONB)


class OutboxEvent(ScopedRecord, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        *scope_constraints("outbox_events"),
        fk("outbox_events", "event_id", "domain_events"),
        UniqueConstraint("organization_id", "event_id", name="uq_outbox_event"),
        states("status", ["PENDING", "LEASED", "RETRY", "DELIVERED", "DEAD"], "ck_outbox_status"),
        CheckConstraint("attempts BETWEEN 0 AND 10", name="ck_outbox_attempts"),
        CheckConstraint(
            "(status = 'LEASED') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)",
            name="ck_outbox_lease",
        ),
        Index("ix_outbox_ready", "organization_id", "status", "available_at"),
    )
    event_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64))


class OutboxDelivery(ScopedRecord, Base):
    __tablename__ = "outbox_deliveries"
    __table_args__ = (
        *scope_constraints("outbox_deliveries"),
        fk("outbox_deliveries", "outbox_id", "outbox_events"),
        UniqueConstraint(
            "organization_id", "outbox_id", "attempt", "phase", name="uq_outbox_delivery"
        ),
        states("phase", ["CLAIMED", "DELIVERED", "FAILED", "EXPIRED"], "ck_delivery_phase"),
    )
    outbox_id: Mapped[UUID]
    attempt: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))


class EventConsumption(ScopedRecord, Base):
    __tablename__ = "event_consumptions"
    __table_args__ = (
        *scope_constraints("event_consumptions"),
        fk("event_consumptions", "event_id", "domain_events"),
        UniqueConstraint("organization_id", "event_id", "consumer", name="uq_event_consumption"),
    )
    event_id: Mapped[UUID]
    consumer: Mapped[str] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(32))


class CaseCommand(ScopedRecord, Base):
    __tablename__ = "case_commands"
    __table_args__ = (
        *scope_constraints("case_commands"),
        fk("case_commands", "case_id", "cases"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_case_command"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "result_case_version"],
            [
                "case_versions.organization_id",
                "case_versions.case_id",
                "case_versions.case_version",
            ],
            name="fk_command_revision",
        ),
    )
    case_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    result_case_version: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSONB)
