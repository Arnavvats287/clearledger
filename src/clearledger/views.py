from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecordView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    version: int
    created_at: datetime


class CustomerView(RecordView):
    external_reference: str
    name: str


class ImportedView(RecordView):
    source_import_id: UUID
    source_row: int
    payload_sha256: str


class AliasView(ImportedView):
    customer_id: UUID
    alias: str
    normalized_alias: str
    verified_by: str
    verified_at: datetime
    evidence_reference: str


class InvoiceView(ImportedView):
    customer_id: UUID
    invoice_number: str
    issued_date: date
    due_date: date
    original_amount_paise: int
    initial_open_amount_paise: int
    open_amount_paise: int
    currency: str
    status: str


class BankView(ImportedView):
    source_system: str
    account_ref: str
    external_transaction_id: str
    occurred_at: datetime
    occurred_at_source: str
    amount_paise: int
    currency: str
    payer_name: str
    memo: str


class ReceiptView(RecordView):
    bank_transaction_id: UUID
    amount_paise: int
    unapplied_amount_paise: int
    currency: str
    status: str


class ImportView(RecordView):
    idempotency_key: UUID
    contract_version: str
    kind: str
    source_name: str
    content_sha256: str
    actor_id: str
    status: str
    row_count: int
    result: dict


class AuditView(RecordView):
    source_import_id: UUID
    actor_id: str
    event_type: str
    entity_id: UUID | None
    source_row: int | None
    details: dict
