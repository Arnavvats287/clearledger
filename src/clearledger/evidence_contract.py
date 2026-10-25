"""Evidence 1.0: source assertions and factual verification, never financial authority."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from clearledger.data_contract import timestamp
from clearledger.document_contract import Category, Span
from clearledger.matching_schemas import Version
from clearledger.remittance_parser import json_positions, unique_json

VERSION: Literal["evidence-1.0"] = "evidence-1.0"
ALGORITHM: Literal["evidence-verifier-v1"] = "evidence-verifier-v1"
Kind = Literal["CONTRACT", "PROMOTION", "WMS", "POD", "TAX", "INVOICE", "REMITTANCE"]
Question = Literal[
    "CLAUSE_LIMIT",
    "PROMOTION_AMOUNT",
    "DELIVERY_SHORTAGE",
    "DELIVERY_DAMAGE",
    "TAX_DOCUMENT",
    "INVOICE_AMOUNT",
    "REMITTANCE_AMOUNT",
]
Paise = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
Quantity = Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:/-]{1,100}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Money(Strict):
    value: Paise
    span: Span


class Units(Strict):
    value: Quantity
    span: Span


class Ref(Strict):
    value: Annotated[str, Field(min_length=1, max_length=200)]
    span: Span


class Clause(Strict):
    type: Literal["CONTRACT"]
    limit: Money
    conditions: Literal["UNASSESSED", "NO_ADDITIONAL_CONDITIONS"] = "UNASSESSED"


class Promotion(Strict):
    type: Literal["PROMOTION"]
    amount: Money
    conditions: Literal["UNASSESSED", "NO_ADDITIONAL_CONDITIONS"] = "UNASSESSED"


class Delivery(Strict):
    type: Literal["WMS", "POD"]
    shipment: Ref
    shipped: Units
    delivered: Units
    damaged: Units
    unit_value: Money
    unit: Literal["EACH"]

    @model_validator(mode="after")
    def quantities(self) -> "Delivery":
        if self.delivered.value > self.shipped.value or self.damaged.value > self.delivered.value:
            raise ValueError("Inconsistent delivery quantities")
        return self


class Tax(Strict):
    type: Literal["TAX"]
    tax_tag: Literal["INCOME_TAX_TDS", "GST_TDS", "UNKNOWN"]
    amount: Money


class Amount(Strict):
    type: Literal["INVOICE", "REMITTANCE"]
    amount: Money


Fact = Annotated[Clause | Promotion | Delivery | Tax | Amount, Field(discriminator="type")]


class RecordInput(Strict):
    contract_version: Literal["evidence-1.0"] = VERSION
    source_system: Identifier
    source_record_id: Identifier
    revision: Version
    previous_id: UUID | None = None
    key_id: Identifier | None = None
    customer_id: UUID
    invoice_id: UUID | None = None
    document_id: UUID
    document_version: Version
    raw_sha256: Hash
    canonical_sha256: Hash
    excerpt: Span
    customer_reference: Ref
    invoice_reference: Ref | None = None
    categories: Annotated[list[Category], Field(min_length=1, max_length=7)]
    effective_from: date
    effective_to: date
    occurred_at: datetime
    recorded_at: datetime
    signed_at: datetime | None = None
    approved_at: datetime | None = None
    date_basis: Literal["INVOICE_ISSUED", "RECEIPT_OCCURRED"]
    fact: Fact
    signature: Hash | None = None

    @field_validator("effective_from", "effective_to", mode="before")
    @classmethod
    def exact_date(cls, value: object) -> object:
        if isinstance(value, str):
            if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
                raise ValueError("Expected YYYY-MM-DD")
        elif type(value) is not date:
            raise ValueError("Expected calendar date")
        return value

    @field_validator("occurred_at", "recorded_at", "signed_at", "approved_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            return timestamp(value)
        if isinstance(value, datetime) and value.tzinfo is not None:
            return timestamp(value.isoformat())
        raise ValueError("Expected timestamp with timezone")

    @model_validator(mode="after")
    def consistency(self) -> "RecordInput":
        if self.effective_to < self.effective_from or self.occurred_at > self.recorded_at:
            raise ValueError("Invalid evidence chronology")
        if any(t is not None and t > self.recorded_at for t in (self.signed_at, self.approved_at)):
            raise ValueError("Status date after source record")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("Duplicate claim categories")
        if (self.invoice_id is None) != (self.invoice_reference is None):
            raise ValueError("Invoice pointer required together")
        if (self.signature is None) != (self.key_id is None):
            raise ValueError("Signature and key ID required together")
        if (
            self.fact.type in {"WMS", "POD", "TAX", "INVOICE", "REMITTANCE"}
            and self.invoice_id is None
        ):
            raise ValueError("Invoice required for transactional evidence")
        return self


class TrustSource(Strict):
    organization_id: UUID
    source_system: Identifier
    key_id: Identifier
    secret: Annotated[str, Field(min_length=32, max_length=256, exclude=True, repr=False)]
    allowed_kinds: Annotated[list[Kind], Field(min_length=1, max_length=7)]


class ScopeInput(Strict):
    expected_case_version: Version
    expected_context_sha256: Hash
    customer_id: UUID
    claim_id: UUID | None = None
    invoice_id: UUID | None = None


class SearchInput(ScopeInput):
    tool: Literal[
        "find_contract_clauses",
        "find_promotions",
        "get_wms_deliveries",
        "get_proof_of_delivery",
        "get_tagged_tax_evidence",
        "get_invoice_evidence",
        "get_remittance_evidence",
    ]
    query: Annotated[str, Field(max_length=256)] = ""
    after_id: UUID | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=50)] = 20

    @field_validator("query")
    @classmethod
    def safe_query(cls, value: str) -> str:
        if len(value.split()) > 32 or any(ord(c) < 32 for c in value):
            raise ValueError("Search query limit")
        value.encode("utf-8", errors="strict")
        return value


def validate_json_body(raw: bytes) -> None:
    value = raw.decode("utf-8", errors="strict")
    json_positions(value)
    nodes: list[object] = [unique_json(value)]
    count = 0
    while nodes:
        item = nodes.pop()
        count += 1
        if count > 2048:
            raise ValueError("Evidence JSON node limit")
        if isinstance(item, dict):
            nodes.extend(item.values())
            nodes.extend(item.keys())
        elif isinstance(item, list):
            nodes.extend(item)


class Citation(Strict):
    record_id: UUID
    document_id: UUID
    document_version: Version
    raw_sha256: Hash
    canonical_sha256: Hash
    span: Span


class VerifyInput(ScopeInput):
    claim_id: UUID
    invoice_id: UUID
    question: Question
    receipt_id: UUID | None = None
    citations: Annotated[list[Citation], Field(max_length=20)]


class RecordView(Strict):
    id: UUID
    revision: int
    kind: Kind
    content_sha256: str
    is_current: bool
    source_authenticated: bool
    citation: Citation
    manifest: RecordInput
    financial_authority: Literal[False] = False
    untrusted_source_content: Literal[True] = True


class Hit(Strict):
    record_type: Literal["DOCUMENT_EVIDENCE", "INVOICE", "REMITTANCE"]
    id: UUID
    version: int
    kind: Kind
    document_id: UUID | None
    document_version: int | None
    raw_sha256: str
    canonical_sha256: str | None
    page: int | None
    start: int | None
    end: int | None
    excerpt: str
    source_authenticated: bool
    source_integrity: bool
    is_current: bool
    metadata: dict[str, object]
    financial_authority: Literal[False] = False
    untrusted_source_content: Literal[True] = True


class NativePointer(Strict):
    record_type: Literal["INVOICE", "REMITTANCE"]
    id: UUID
    version: int
    raw_sha256: str
    source_import_id: UUID | None = None
    source_row: int | None = None
    document_id: UUID | None = None
    document_version: int | None = None
    span: Span | None = None
    payload: dict[str, object]
    source_current: bool
    source_authenticated: Literal[False] = False
    financial_authority: Literal[False] = False


class SearchResult(Strict):
    algorithm: Literal["evidence-verifier-v1"] = ALGORITHM
    items: list[Hit]
    has_more: bool
    next_after_id: UUID | None
    search_complete: bool
    reasons: list[str]
    input_sha256: str
    financial_authority: Literal[False] = False


class Finding(Strict):
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "NOT_APPLICABLE"]
    reasons: list[str]
    record_ids: list[UUID]


class Verification(Strict):
    algorithm: Literal["evidence-verifier-v1"] = ALGORITHM
    purpose: Literal["SOURCE_FACTS_ONLY"] = "SOURCE_FACTS_ONLY"
    outcome: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "NOT_APPLICABLE"]
    reasons: list[str]
    findings: list[Finding]
    input_sha256: str
    search_complete: bool
    requires_human_review: Literal[True] = True
    financial_authority: Literal[False] = False
