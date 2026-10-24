from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
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
