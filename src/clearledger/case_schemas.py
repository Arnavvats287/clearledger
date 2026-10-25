from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clearledger.case_domain import CaseState, ClaimState
from clearledger.document_contract import Span
from clearledger.matching_schemas import Version


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class VersionInput(Input):
    expected_case_version: Version


class TransitionInput(VersionInput):
    target: CaseState


class ClaimTransitionInput(VersionInput):
    expected_claim_version: Version
    target: ClaimState


class AttachInput(VersionInput):
    document_id: UUID
    document_version: Version
    raw_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    canonical_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    span: Span
    relation: Literal["CONTEXT", "SUPPORTS", "CONTRADICTS"] = "CONTEXT"
    claim_ids: Annotated[list[UUID], Field(max_length=100)] = Field(default_factory=list)
    invoice_id: UUID | None = None
    invoice_reference_span: Span | None = None


class BindInput(VersionInput):
    matching_proposal_id: UUID


class ReconcileInput(Input):
    source: Literal["receipts", "document_events", "matching_proposals", "matching_evidence"]
    after_id: UUID | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 100


class CaseView(BaseModel):
    id: UUID
    requested_case_id: UUID
    organization_id: UUID
    version: int
    state: CaseState
    customer_id: UUID | None
    created_at: datetime
    context_sha256: str
    current_context_sha256: str
    is_stale: bool
    attention_codes: list[str]
    receipt_ids: list[UUID]
    document_ids: list[UUID]
    invoice_ids: list[UUID]
    claimed_total_paise: int | None
    unknown_amount_count: int
    requires_human_review: Literal[True] = True
    financial_authority: Literal[False] = False
    verified_settled_paise: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)] = 0


class ClaimView(BaseModel):
    id: UUID
    case_id: UUID
    canonical_case_id: UUID
    version: int
    state: ClaimState
    category: str
    amount_paise: int | None
    document_id: UUID
    assertion: dict[str, object]
    source_current: bool
    requires_human_review: Literal[True] = True
    financial_authority: Literal[False] = False


class HistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    created_at: datetime
    case_id: UUID | None = None
    case_version: int | None = None
    event_type: str | None = None
    actor_id: str | None = None
    snapshot: dict[str, object] | None = None
    payload: dict[str, object] | None = None


class EvidenceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    case_id: UUID
    claim_id: UUID | None
    document_id: UUID
    document_version: int
    raw_sha256: str
    canonical_sha256: str
    span: Span
    relation: str
    actor_id: str
    financial_authority: Literal[False] = False
    source_authenticity: Literal["UNVERIFIED"] = "UNVERIFIED"


class HypothesisView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    claim_id: UUID
    basis_case_id: UUID
    basis_case_version: int
    content: dict[str, object]
    is_stale: bool


class BindingView(BaseModel):
    id: UUID
    matching_proposal_id: UUID
    basis_case_version: int
    is_stale: bool
    financial_authority: Literal[False] = False


class WorkView(BaseModel):
    id: UUID
    event_id: UUID
    event_type: str
    status: str
    attempts: int
    available_at: datetime
    last_error_code: str | None


class ReconcileView(BaseModel):
    published: int
    next_after_id: UUID | None
    has_more: bool


class ReevaluationPayload(Input):
    affected_claim_ids: Annotated[list[UUID], Field(max_length=2000)]
    cause_event_id: UUID


class ClaimHistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    claim_id: UUID
    claim_version: int
    event_id: UUID
    snapshot: dict[str, object]
    created_at: datetime


class ReevaluationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID
    scheduled_version: int
    evaluated_version: int
    result: dict[str, object]
    created_at: datetime
