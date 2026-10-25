"""Review-1.0: operational actions never imply financial or customer authority."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, model_validator

from clearledger.case_schemas import AttachInput
from clearledger.evidence_contract import Hash, Strict
from clearledger.matching_schemas import Version

Role = Literal["AR_ANALYST", "CONTROLLER", "AUDITOR"]
Reason = Literal[
    "MISSING_EVIDENCE",
    "CONTRADICTORY_EVIDENCE",
    "CUSTOMER_FOLLOW_UP",
    "REVIEW_COMMENT",
    "CUSTOMER_RESPONSE",
    "SETTLED_AND_COMPLETE",
    "NEW_INFORMATION",
]


class Login(Strict):
    username: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")]
    password: SecretStr


class LoginResult(Strict):
    access_token: str = Field(repr=False)
    expires_at: datetime
    authority: Literal["LOCAL_DEMO_ONLY"] = "LOCAL_DEMO_ONLY"
    financial_authority: Literal[False] = False


class Basis(Strict):
    expected_case_version: Version
    expected_context_sha256: Hash


class Note(Basis):
    reason: Reason
    comment: Annotated[str, Field(max_length=2000)] = ""


class DraftInput(Note):
    invoice_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)]
    claim_ids: Annotated[list[UUID], Field(max_length=20)] = Field(default_factory=list)
    delivery_record_ids: Annotated[list[UUID], Field(max_length=20)] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self) -> "DraftInput":
        if self.reason not in {"CUSTOMER_FOLLOW_UP", "MISSING_EVIDENCE", "CONTRADICTORY_EVIDENCE"}:
            raise ValueError("Draft correspondence reason required")
        for ids in (self.invoice_ids, self.claim_ids, self.delivery_record_ids):
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate source ID")
        return self


class EvidenceRequest(Note):
    claim_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)]
    proposal_id: UUID | None = None
    expected_proposal_version: Version | None = None
    expected_snapshot_sha256: Hash | None = None

    @model_validator(mode="after")
    def proposal_binding(self) -> "EvidenceRequest":
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("Duplicate claim ID")
        if (
            len(
                {
                    self.proposal_id is None,
                    self.expected_proposal_version is None,
                    self.expected_snapshot_sha256 is None,
                }
            )
            != 1
        ):
            raise ValueError("Complete proposal binding required")
        if self.reason not in {"MISSING_EVIDENCE", "CONTRADICTORY_EVIDENCE"}:
            raise ValueError("Evidence reason required")
        return self


class ResponseInput(Note):
    evidence: AttachInput
    expected_claim_versions: Annotated[dict[UUID, Version], Field(max_length=20)]
    in_reply_to: UUID | None = None

    @model_validator(mode="after")
    def exact_targets(self) -> "ResponseInput":
        if (
            set(self.evidence.claim_ids) != set(self.expected_claim_versions)
            or len(self.evidence.claim_ids) != len(set(self.evidence.claim_ids))
            or self.evidence.expected_case_version != self.expected_case_version
            or self.reason != "CUSTOMER_RESPONSE"
        ):
            raise ValueError("Exact response target versions required")
        return self


class ActionView(Strict):
    id: UUID
    case_id: UUID
    kind: str
    basis_case_version: int
    result_case_version: int
    actor: dict[str, object]
    content: dict[str, object]
    source_sha256: str
    created_at: datetime
    is_stale: bool
    transmitted: Literal[False] = False
    financial_authority: Literal[False] = False
