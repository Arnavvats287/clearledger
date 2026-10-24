"""DATA_CONTRACT 1.0 input validation. No dataset construction."""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

CONTRACT_VERSION = "1.0"
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000
MAX_PAISE = 2**63 - 1
Reference = Annotated[str, StringConstraints(min_length=1, max_length=100)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
PositivePaise = Annotated[int, Field(strict=True, ge=1, le=MAX_PAISE)]
NonnegativePaise = Annotated[int, Field(strict=True, ge=0, le=MAX_PAISE)]


def timestamp(value: str) -> datetime:
    if not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
        value,
    ):
        raise ValueError("Expected an ISO timestamp with seconds and explicit timezone")
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError("Timestamp must represent a valid UTC calendar instant") from exc


class InputRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("Whitespace padding and control characters are forbidden")
        return value


class CustomerInput(InputRow):
    external_reference: Reference
    name: Name


class AliasInput(InputRow):
    customer_reference: Reference
    alias: Name
    verified_by: Reference
    verified_at: Annotated[str, Field(max_length=40)]
    evidence_reference: Name

    @field_validator("alias")
    @classmethod
    def bounded_normalization(cls, value):
        if len(" ".join(value.split()).casefold()) > 200:
            raise ValueError("Normalized alias exceeds 200 characters")
        return value

    @field_validator("verified_at")
    @classmethod
    def valid_timestamp(cls, value):
        timestamp(value)
        return value


class InvoiceInput(InputRow):
    customer_reference: Reference
    invoice_number: Reference
    issued_date: date
    due_date: date
    original_amount_paise: PositivePaise
    open_amount_paise: NonnegativePaise
    currency: Literal["INR"]

    @field_validator("issued_date", "due_date", mode="before")
    @classmethod
    def strict_date(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Expected YYYY-MM-DD")
        return date.fromisoformat(value)

    @model_validator(mode="after")
    def consistent(self):
        if self.due_date < self.issued_date:
            raise ValueError("due_date must be on or after issued_date")
        if self.open_amount_paise > self.original_amount_paise:
            raise ValueError("open_amount_paise exceeds original_amount_paise")
        return self


class BankInput(InputRow):
    source_system: Reference
    account_ref: Reference
    external_transaction_id: Reference
    occurred_at: Annotated[str, Field(max_length=40)]
    amount_paise: PositivePaise
    currency: Literal["INR"]
    payer_name: Annotated[str, Field(max_length=200)]
    memo: Annotated[str, Field(max_length=2000)]

    @field_validator("occurred_at")
    @classmethod
    def valid_timestamp(cls, value):
        timestamp(value)
        return value


INPUTS = {
    "customers": CustomerInput,
    "payer-aliases": AliasInput,
    "invoices": InvoiceInput,
    "bank-transactions": BankInput,
}
