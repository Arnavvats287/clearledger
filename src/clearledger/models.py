from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_reference", name="uq_customer_org_reference"),
        Index("ix_customers_organization_id", "organization_id"),
        UniqueConstraint("organization_id", "id", name="uq_customers_org_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    external_reference: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScopedRecord:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def scope_constraints(table: str):
    return (
        UniqueConstraint("organization_id", "id", name=f"uq_{table}_org_id"),
        CheckConstraint("version > 0", name=f"ck_{table}_version"),
        Index(f"ix_{table}_organization_id", "organization_id"),
    )


def source_constraint(table: str):
    return ForeignKeyConstraint(
        ["organization_id", "source_import_id"],
        ["source_imports.organization_id", "source_imports.id"],
        name=f"fk_{table}_source",
    )


class SourceImport(ScopedRecord, Base):
    __tablename__ = "source_imports"
    __table_args__ = (
        *scope_constraints("source_imports"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_import_idempotency"),
        CheckConstraint("status IN ('PROCESSING','ACCEPTED','REJECTED')", name="ck_import_status"),
        CheckConstraint("row_count BETWEEN 0 AND 10000", name="ck_import_rows"),
        CheckConstraint("octet_length(raw_bytes) <= 2097152", name="ck_import_size"),
    )
    idempotency_key: Mapped[UUID]
    contract_version: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(128))
    content_sha256: Mapped[str] = mapped_column(String(64))
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    actor_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    row_count: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSONB)


class ImportedRecord(ScopedRecord):
    source_import_id: Mapped[UUID]
    source_row: Mapped[int] = mapped_column(Integer)
    payload_sha256: Mapped[str] = mapped_column(String(64))


class PayerAlias(ImportedRecord, Base):
    __tablename__ = "payer_aliases"
    __table_args__ = (
        *scope_constraints("payer_aliases"),
        source_constraint("payer_aliases"),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_alias_customer",
        ),
        UniqueConstraint("organization_id", "normalized_alias", name="uq_alias_org_normalized"),
    )
    customer_id: Mapped[UUID]
    alias: Mapped[str] = mapped_column(String(200))
    normalized_alias: Mapped[str] = mapped_column(String(200))
    verified_by: Mapped[str] = mapped_column(String(100))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_reference: Mapped[str] = mapped_column(String(200))


class Invoice(ImportedRecord, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        *scope_constraints("invoices"),
        source_constraint("invoices"),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_invoice_customer",
        ),
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_org_number"),
        UniqueConstraint("organization_id", "id", "customer_id", name="uq_invoice_org_id_customer"),
        CheckConstraint("currency = 'INR'", name="ck_invoice_currency"),
        CheckConstraint("original_amount_paise > 0", name="ck_invoice_positive"),
        CheckConstraint(
            "0 <= open_amount_paise AND open_amount_paise <= initial_open_amount_paise "
            "AND initial_open_amount_paise <= original_amount_paise",
            name="ck_invoice_balances",
        ),
        CheckConstraint("due_date >= issued_date", name="ck_invoice_dates"),
        CheckConstraint(
            "(status = 'OPEN' AND open_amount_paise > 0) OR "
            "(status = 'CLOSED' AND open_amount_paise = 0)",
            name="ck_invoice_status",
        ),
        Index("ix_invoices_org_customer_status", "organization_id", "customer_id", "status"),
    )
    customer_id: Mapped[UUID]
    invoice_number: Mapped[str] = mapped_column(String(100))
    issued_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    original_amount_paise: Mapped[int] = mapped_column(BigInteger)
    initial_open_amount_paise: Mapped[int] = mapped_column(BigInteger)
    open_amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20))


class BankTransaction(ImportedRecord, Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        *scope_constraints("bank_transactions"),
        source_constraint("bank_transactions"),
        UniqueConstraint(
            "organization_id",
            "source_system",
            "account_ref",
            "external_transaction_id",
            name="uq_bank_source_identity",
        ),
        UniqueConstraint("organization_id", "id", "amount_paise", name="uq_bank_org_id_amount"),
        CheckConstraint("amount_paise > 0", name="ck_bank_positive"),
        CheckConstraint("currency = 'INR'", name="ck_bank_currency"),
    )
    source_system: Mapped[str] = mapped_column(String(100))
    account_ref: Mapped[str] = mapped_column(String(100))
    external_transaction_id: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurred_at_source: Mapped[str] = mapped_column(String(40))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    payer_name: Mapped[str] = mapped_column(String(200))
    memo: Mapped[str] = mapped_column(String(2000))


class Receipt(ScopedRecord, Base):
    __tablename__ = "receipts"
    __table_args__ = (
        *scope_constraints("receipts"),
        ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id", "amount_paise"],
            [
                "bank_transactions.organization_id",
                "bank_transactions.id",
                "bank_transactions.amount_paise",
            ],
            name="fk_receipt_bank_amount",
        ),
        UniqueConstraint("organization_id", "bank_transaction_id", name="uq_receipt_bank"),
        CheckConstraint("currency = 'INR'", name="ck_receipt_currency"),
        CheckConstraint("amount_paise > 0", name="ck_receipt_positive"),
        CheckConstraint(
            "unapplied_amount_paise BETWEEN 0 AND amount_paise", name="ck_receipt_balance"
        ),
        CheckConstraint(
            "(status = 'UNAPPLIED' AND unapplied_amount_paise = amount_paise) OR "
            "(status = 'PARTIALLY_APPLIED' AND unapplied_amount_paise > 0 "
            "AND unapplied_amount_paise < amount_paise) OR "
            "(status = 'FULLY_APPLIED' AND unapplied_amount_paise = 0)",
            name="ck_receipt_status",
        ),
    )
    bank_transaction_id: Mapped[UUID]
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    unapplied_amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20))


class AuditEvent(ScopedRecord, Base):
    __tablename__ = "audit_events"
    __table_args__ = (*scope_constraints("audit_events"), source_constraint("audit_events"))
    source_import_id: Mapped[UUID]
    actor_id: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID | None]
    source_row: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSONB)


class MatchingEvidence(ScopedRecord, Base):
    __tablename__ = "matching_evidence"
    __table_args__ = (
        *scope_constraints("matching_evidence"),
        source_constraint("matching_evidence"),
        ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["receipts.organization_id", "receipts.id"],
            name="fk_evidence_receipt",
        ),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_evidence_customer",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "customer_id"],
            ["invoices.organization_id", "invoices.id", "invoices.customer_id"],
            name="fk_evidence_invoice_owner",
        ),
        UniqueConstraint(
            "organization_id", "receipt_id", "payload_sha256", name="uq_matching_evidence_payload"
        ),
        CheckConstraint(
            "kind IN ('CUSTOMER_MAPPING','INVOICE_REFERENCE')", name="ck_matching_evidence_kind"
        ),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset", name="ck_matching_evidence_span"
        ),
        CheckConstraint(
            "receipt_version > 0 AND customer_version > 0", name="ck_matching_evidence_versions"
        ),
        CheckConstraint(
            "(kind = 'CUSTOMER_MAPPING' AND invoice_id IS NULL AND invoice_version IS NULL) OR "
            "(kind = 'INVOICE_REFERENCE' AND invoice_id IS NOT NULL "
            "AND invoice_version IS NOT NULL AND invoice_version > 0)",
            name="ck_matching_evidence_invoice",
        ),
    )
    receipt_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    invoice_id: Mapped[UUID | None]
    receipt_version: Mapped[int] = mapped_column(Integer)
    customer_version: Mapped[int] = mapped_column(Integer)
    invoice_version: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    source_import_id: Mapped[UUID]
    source_row: Mapped[int] = mapped_column(Integer)
    source_field: Mapped[str] = mapped_column(String(20))
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    exact_quote: Mapped[str] = mapped_column(String(2000))
    verified_by: Mapped[str] = mapped_column(String(100))
    payload_sha256: Mapped[str] = mapped_column(String(64))


class MatchingProposal(ScopedRecord, Base):
    __tablename__ = "matching_proposals"
    __table_args__ = (
        *scope_constraints("matching_proposals"),
        source_constraint("matching_proposals"),
        ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["receipts.organization_id", "receipts.id"],
            name="fk_matching_proposal_receipt",
        ),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_matching_proposal_customer",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "customer_id"],
            ["invoices.organization_id", "invoices.id", "invoices.customer_id"],
            name="fk_matching_proposal_invoice",
        ),
        UniqueConstraint(
            "organization_id", "receipt_id", "snapshot_sha256", name="uq_matching_proposal_snapshot"
        ),
        CheckConstraint(
            "outcome IN ('EXACT_MATCH','AMBIGUOUS','NO_SUPPORTED_MATCH',"
            "'UNIQUE','UNRESOLVED','SEARCH_INCOMPLETE')",
            name="ck_matching_proposal_outcome",
        ),
        CheckConstraint(
            "(outcome = 'EXACT_MATCH' AND amount_paise > 0 AND invoice_id IS NOT NULL "
            "AND customer_id IS NOT NULL) OR "
            "(outcome <> 'EXACT_MATCH' AND amount_paise = 0 AND invoice_id IS NULL)",
            name="ck_matching_proposal_amount",
        ),
    )
    receipt_id: Mapped[UUID]
    source_import_id: Mapped[UUID]
    customer_id: Mapped[UUID | None]
    invoice_id: Mapped[UUID | None]
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    outcome: Mapped[str] = mapped_column(String(32))
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)


class MatchingRequest(ScopedRecord, Base):
    __tablename__ = "matching_requests"
    __table_args__ = (
        *scope_constraints("matching_requests"),
        ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["receipts.organization_id", "receipts.id"],
            name="fk_matching_request_receipt",
        ),
        ForeignKeyConstraint(
            ["organization_id", "evidence_id"],
            ["matching_evidence.organization_id", "matching_evidence.id"],
            name="fk_matching_request_evidence",
        ),
        ForeignKeyConstraint(
            ["organization_id", "proposal_id"],
            ["matching_proposals.organization_id", "matching_proposals.id"],
            name="fk_matching_request_proposal",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_matching_request_key"),
        CheckConstraint(
            "(evidence_id IS NULL) <> (proposal_id IS NULL)", name="ck_matching_request_target"
        ),
    )
    receipt_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    evidence_id: Mapped[UUID | None]
    proposal_id: Mapped[UUID | None]


def document_fk(table: str):
    return ForeignKeyConstraint(
        ["organization_id", "document_id"],
        ["documents.organization_id", "documents.id"],
        name=f"fk_{table}_document",
    )


class Document(ScopedRecord, Base):
    __tablename__ = "documents"
    __table_args__ = (
        *scope_constraints("documents"),
        UniqueConstraint("organization_id", "content_sha256", name="uq_document_content"),
        CheckConstraint("size_bytes BETWEEN 1 AND 2097152", name="ck_document_size"),
        CheckConstraint(
            "parse_status IN ('READY','NEEDS_OCR','PARSE_FAILED')", name="ck_document_status"
        ),
        CheckConstraint(
            "mime IN ('application/pdf','message/rfc822','text/plain','application/json')",
            name="ck_document_mime",
        ),
    )
    content_sha256: Mapped[str] = mapped_column(String(64))
    canonical_sha256: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(128))
    mime: Mapped[str] = mapped_column(String(64))
    document_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    synthetic_approved: Mapped[bool] = mapped_column(Boolean)
    pages: Mapped[list] = mapped_column(JSONB)
    parser_version: Mapped[str] = mapped_column(String(40))
    parse_status: Mapped[str] = mapped_column(String(32))
    parse_error: Mapped[str | None] = mapped_column(String(64))


class DocumentExtraction(ScopedRecord, Base):
    __tablename__ = "document_extractions"
    __table_args__ = (
        *scope_constraints("document_extractions"),
        document_fk("document_extractions"),
        UniqueConstraint(
            "organization_id", "document_id", "input_sha256", name="uq_extraction_input"
        ),
        UniqueConstraint(
            "organization_id", "document_id", "extraction_version", name="uq_extraction_version"
        ),
        UniqueConstraint("organization_id", "id", "document_id", name="uq_extraction_document"),
        CheckConstraint("extraction_version > 0", name="ck_extraction_version"),
        CheckConstraint(
            "status IN ('SUCCEEDED','NEEDS_REVIEW','FAILED','BLOCKED')", name="ck_extraction_status"
        ),
    )
    document_id: Mapped[UUID]
    extraction_version: Mapped[int] = mapped_column(Integer)
    input_sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(40))
    route: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    inputs: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    metrics: Mapped[dict] = mapped_column(JSONB)


class DocumentAssociation(ScopedRecord, Base):
    __tablename__ = "document_associations"
    __table_args__ = (
        *scope_constraints("document_associations"),
        document_fk("document_associations"),
        ForeignKeyConstraint(
            ["organization_id", "extraction_id", "document_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.id",
                "document_extractions.document_id",
            ],
            name="fk_association_extraction",
        ),
        ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["receipts.organization_id", "receipts.id"],
            name="fk_association_receipt",
        ),
        UniqueConstraint(
            "organization_id", "document_id", "input_sha256", name="uq_document_association"
        ),
        CheckConstraint(
            "status IN ('LINKED','CANDIDATES','UNRESOLVED','SEARCH_INCOMPLETE')",
            name="ck_association_status",
        ),
        CheckConstraint(
            "(status = 'LINKED') = (receipt_id IS NOT NULL)", name="ck_association_target"
        ),
    )
    document_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    receipt_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(32))
    input_sha256: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)


class DocumentOperation(ScopedRecord, Base):
    __tablename__ = "document_operations"
    __table_args__ = (
        *scope_constraints("document_operations"),
        document_fk("document_operations"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_document_operation_key"),
        ForeignKeyConstraint(
            ["organization_id", "extraction_id"],
            ["document_extractions.organization_id", "document_extractions.id"],
            name="fk_document_operation_extraction",
        ),
        ForeignKeyConstraint(
            ["organization_id", "association_id"],
            ["document_associations.organization_id", "document_associations.id"],
            name="fk_document_operation_association",
        ),
        CheckConstraint(
            "(operation = 'UPLOAD' AND extraction_id IS NULL AND association_id IS NULL) OR "
            "(operation = 'EXTRACT' AND extraction_id IS NOT NULL AND association_id IS NULL) OR "
            "(operation = 'CORRELATE' AND association_id IS NOT NULL AND extraction_id IS NULL)",
            name="ck_document_operation",
        ),
    )
    document_id: Mapped[UUID]
    idempotency_key: Mapped[UUID]
    request_sha256: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(16))
    extraction_id: Mapped[UUID | None]
    association_id: Mapped[UUID | None]


class DocumentEvent(ScopedRecord, Base):
    __tablename__ = "document_events"
    __table_args__ = (*scope_constraints("document_events"), document_fk("document_events"))
    document_id: Mapped[UUID]
    actor_id: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID]
    details: Mapped[dict] = mapped_column(JSONB)


class ProviderReservation(ScopedRecord, Base):
    """Committed independently of extraction; failed/crashed attempts retain their budget."""

    __tablename__ = "provider_reservations"
    __table_args__ = (
        *scope_constraints("provider_reservations"),
        Index("ix_provider_reservation_day", "organization_id", "provider", "quota_day"),
        CheckConstraint("requests = 3", name="ck_provider_reserved_requests"),
        CheckConstraint("input_tokens BETWEEN 1 AND 1000000", name="ck_provider_reserved_input"),
        CheckConstraint("output_tokens BETWEEN 1 AND 4096", name="ck_provider_reserved_output"),
        CheckConstraint("provider IN ('gemini','fake')", name="ck_provider_reservation_name"),
    )
    provider: Mapped[str] = mapped_column(String(16))
    quota_day: Mapped[date] = mapped_column(Date)
    requests: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
