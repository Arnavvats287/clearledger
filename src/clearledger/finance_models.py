"""Scoped accounting simulation records and immutable provenance."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearledger.case_models import fk
from clearledger.models import Base, ScopedRecord, scope_constraints


class FinancePolicy(ScopedRecord, Base):
    __tablename__ = "finance_policies"
    __table_args__ = (
        *scope_constraints("finance_policies"),
        fk("finance_policies", "previous_id", "finance_policies"),
        UniqueConstraint(
            "organization_id", "reference", "policy_version", name="uq_finance_policy_version"
        ),
        UniqueConstraint("organization_id", "previous_id", name="uq_finance_policy_successor"),
        CheckConstraint("policy_version > 0", name="ck_finance_policy_version"),
    )
    reference: Mapped[str] = mapped_column(String(100))
    policy_version: Mapped[int]
    previous_id: Mapped[UUID | None]
    spec: Mapped[dict] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    reviewer: Mapped[dict] = mapped_column(JSONB)


class FinanceSourceReview(ScopedRecord, Base):
    __tablename__ = "finance_source_reviews"
    __table_args__ = (
        *scope_constraints("finance_source_reviews"),
        fk("finance_source_reviews", "case_id", "cases"),
        fk("finance_source_reviews", "receipt_id", "receipts"),
        fk("finance_source_reviews", "customer_id", "customers"),
        fk("finance_source_reviews", "matching_proposal_id", "matching_proposals"),
    )
    case_id: Mapped[UUID]
    receipt_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    matching_proposal_id: Mapped[UUID]
    snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    reviewer: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinanceProposal(ScopedRecord, Base):
    __tablename__ = "finance_proposals"
    __table_args__ = (
        *scope_constraints("finance_proposals"),
        fk("finance_proposals", "case_id", "cases"),
        fk("finance_proposals", "receipt_id", "receipts"),
        fk("finance_proposals", "policy_id", "finance_policies"),
        fk("finance_proposals", "source_review_id", "finance_source_reviews"),
        UniqueConstraint(
            "organization_id", "snapshot_sha256", "maker_identity", name="uq_finance_proposal_input"
        ),
        CheckConstraint(
            "state IN ('DRAFT','VALIDATED','PENDING_APPROVAL','APPROVED','REJECTED',"
            "'INVALIDATED','SIMULATED_POSTED')",
            name="ck_finance_proposal_state",
        ),
    )
    case_id: Mapped[UUID]
    receipt_id: Mapped[UUID]
    policy_id: Mapped[UUID]
    source_review_id: Mapped[UUID]
    maker_identity: Mapped[str] = mapped_column(String(210))
    maker: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(24), default="DRAFT")
    snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    journals: Mapped[list] = mapped_column(JSONB)
    treatments: Mapped[list] = mapped_column(JSONB)


class FinanceProposalEvent(ScopedRecord, Base):
    __tablename__ = "finance_proposal_events"
    __table_args__ = (
        *scope_constraints("finance_proposal_events"),
        fk("finance_proposal_events", "proposal_id", "finance_proposals"),
        UniqueConstraint(
            "organization_id", "proposal_id", "proposal_version", name="uq_finance_proposal_history"
        ),
    )
    proposal_id: Mapped[UUID]
    proposal_version: Mapped[int]
    state: Mapped[str] = mapped_column(String(24))
    actor: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(64))


class FinanceApproval(ScopedRecord, Base):
    __tablename__ = "finance_approvals"
    __table_args__ = (
        *scope_constraints("finance_approvals"),
        fk("finance_approvals", "proposal_id", "finance_proposals"),
        UniqueConstraint("organization_id", "proposal_id", name="uq_finance_approval"),
        ForeignKeyConstraint(
            ["organization_id", "proposal_id", "proposal_version"],
            [
                "finance_proposal_events.organization_id",
                "finance_proposal_events.proposal_id",
                "finance_proposal_events.proposal_version",
            ],
            name="fk_finance_approval_version",
        ),
    )
    proposal_id: Mapped[UUID]
    proposal_version: Mapped[int]
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    approver_identity: Mapped[str] = mapped_column(String(210))
    approver: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerJournal(ScopedRecord, Base):
    __tablename__ = "ledger_journals"
    __table_args__ = (
        *scope_constraints("ledger_journals"),
        fk("ledger_journals", "proposal_id", "finance_proposals"),
        fk("ledger_journals", "receipt_id", "receipts"),
        fk("ledger_journals", "policy_id", "finance_policies"),
        fk("ledger_journals", "source_review_id", "finance_source_reviews"),
        CheckConstraint("kind IN ('BANK','APPLICATION')", name="ck_ledger_journal_kind"),
        Index(
            "uq_ledger_bank_receipt",
            "organization_id",
            "receipt_id",
            unique=True,
            postgresql_where=text("kind = 'BANK'"),
        ),
        Index(
            "uq_ledger_application",
            "organization_id",
            "proposal_id",
            unique=True,
            postgresql_where=text("kind = 'APPLICATION'"),
        ),
    )
    proposal_id: Mapped[UUID | None]
    receipt_id: Mapped[UUID]
    policy_id: Mapped[UUID]
    source_review_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(String(16))
    actor: Mapped[dict] = mapped_column(JSONB)
    source_sha256: Mapped[str] = mapped_column(String(64))


class LedgerLine(ScopedRecord, Base):
    __tablename__ = "ledger_lines"
    __table_args__ = (
        *scope_constraints("ledger_lines"),
        fk("ledger_lines", "journal_id", "ledger_journals"),
        fk("ledger_lines", "invoice_id", "invoices"),
        UniqueConstraint(
            "organization_id", "journal_id", "line_number", name="uq_ledger_line_number"
        ),
        CheckConstraint(
            "debit_paise>=0 AND credit_paise>=0 AND "
            "((debit_paise>0 AND credit_paise=0) OR (debit_paise=0 AND credit_paise>0))",
            name="ck_ledger_line_amount",
        ),
    )
    journal_id: Mapped[UUID]
    line_number: Mapped[int]
    account_role: Mapped[str] = mapped_column(String(16))
    account_code: Mapped[str] = mapped_column(String(8))
    debit_paise: Mapped[int] = mapped_column(BigInteger)
    credit_paise: Mapped[int] = mapped_column(BigInteger)
    invoice_id: Mapped[UUID | None]


class CashAllocation(ScopedRecord, Base):
    __tablename__ = "cash_allocations"
    __table_args__ = (
        *scope_constraints("cash_allocations"),
        fk("cash_allocations", "journal_id", "ledger_journals"),
        fk("cash_allocations", "proposal_id", "finance_proposals"),
        fk("cash_allocations", "receipt_id", "receipts"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "customer_id"],
            ["invoices.organization_id", "invoices.id", "invoices.customer_id"],
            name="fk_cash_allocation_owner",
        ),
        UniqueConstraint(
            "organization_id", "proposal_id", "invoice_id", name="uq_cash_application_invoice"
        ),
        CheckConstraint("amount_paise>0", name="ck_cash_allocation_amount"),
    )
    journal_id: Mapped[UUID]
    proposal_id: Mapped[UUID]
    receipt_id: Mapped[UUID]
    invoice_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    amount_paise: Mapped[int] = mapped_column(BigInteger)


class NoncashSettlement(ScopedRecord, Base):
    __tablename__ = "noncash_settlements"
    __table_args__ = (
        *scope_constraints("noncash_settlements"),
        fk("noncash_settlements", "journal_id", "ledger_journals"),
        fk("noncash_settlements", "proposal_id", "finance_proposals"),
        fk("noncash_settlements", "claim_id", "claims"),
        fk("noncash_settlements", "policy_id", "finance_policies"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "customer_id"],
            ["invoices.organization_id", "invoices.id", "invoices.customer_id"],
            name="fk_noncash_settlement_owner",
        ),
        UniqueConstraint("organization_id", "claim_id", name="uq_noncash_claim"),
        CheckConstraint("amount_paise>0", name="ck_noncash_amount"),
    )
    journal_id: Mapped[UUID]
    proposal_id: Mapped[UUID]
    policy_id: Mapped[UUID]
    claim_id: Mapped[UUID]
    invoice_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    rule_id: Mapped[str] = mapped_column(String(100))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    evidence_ids: Mapped[list] = mapped_column(JSONB)


class AccountBalance(ScopedRecord, Base):
    __tablename__ = "account_balances"
    __table_args__ = (
        *scope_constraints("account_balances"),
        UniqueConstraint("organization_id", "account_code", name="uq_account_balance"),
    )
    account_code: Mapped[str] = mapped_column(String(8))
    balance_paise: Mapped[int] = mapped_column(BigInteger)


class FinanceCommand(ScopedRecord, Base):
    __tablename__ = "finance_commands"
    __table_args__ = (
        *scope_constraints("finance_commands"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_finance_command"),
    )
    idempotency_key: Mapped[UUID]
    operation: Mapped[str] = mapped_column(String(32))
    request_sha256: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    actor: Mapped[dict] = mapped_column(JSONB)


class FinanceAudit(ScopedRecord, Base):
    __tablename__ = "finance_audit"
    __table_args__ = (
        *scope_constraints("finance_audit"),
        fk("finance_audit", "policy_id", "finance_policies"),
        fk("finance_audit", "source_review_id", "finance_source_reviews"),
        fk("finance_audit", "proposal_id", "finance_proposals"),
        fk("finance_audit", "journal_id", "ledger_journals"),
        CheckConstraint(
            "num_nonnulls(policy_id,source_review_id,proposal_id,journal_id)>=1",
            name="ck_finance_audit_source",
        ),
    )
    policy_id: Mapped[UUID | None]
    source_review_id: Mapped[UUID | None]
    proposal_id: Mapped[UUID | None]
    journal_id: Mapped[UUID | None]
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[dict] = mapped_column(JSONB)
    data: Mapped[dict] = mapped_column(JSONB)
