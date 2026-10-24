from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Version = Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["CUSTOMER_MAPPING", "INVOICE_REFERENCE"]
    customer_id: UUID
    invoice_id: UUID | None = None
    expected_receipt_version: Version
    expected_customer_version: Version
    expected_invoice_version: Version | None = None
    source_import_id: UUID
    source_row: Annotated[int, Field(strict=True, ge=2, le=10001)]
    source_field: Literal["payer_name", "memo"]
    start_offset: Annotated[int, Field(strict=True, ge=0, le=2000)]
    end_offset: Annotated[int, Field(strict=True, ge=1, le=2000)]
    exact_quote: Annotated[str, Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def consistent(self):
        if self.end_offset <= self.start_offset or not self.exact_quote.strip():
            raise ValueError("A nonempty, increasing source span is required")
        if self.kind == "INVOICE_REFERENCE":
            if self.source_field != "memo":
                raise ValueError("Invoice references must cite the bank memo")
            if self.invoice_id is None or self.expected_invoice_version is None:
                raise ValueError(
                    "Invoice references require invoice_id and expected_invoice_version"
                )
        elif self.invoice_id is not None or self.expected_invoice_version is not None:
            raise ValueError("Customer mappings cannot select an invoice")
        return self


class MatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_receipt_version: Version
    expected_invoice_versions: Annotated[dict[UUID, Version], Field(max_length=100)] = Field(
        default_factory=dict
    )
    expected_snapshot_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
