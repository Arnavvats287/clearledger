"""Typed hypotheses, not permissions. Safe provider payloads contain no backend capabilities."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from clearledger.document_contract import Category
from clearledger.evidence_contract import Hash, Hit, Question, Strict, Verification
from clearledger.matching_schemas import Version

ALGORITHM = "director-investigator-v1"
Tool = Literal[
    "find_contract_clauses",
    "find_promotions",
    "get_wms_deliveries",
    "get_proof_of_delivery",
    "get_tagged_tax_evidence",
    "get_invoice_evidence",
    "get_remittance_evidence",
]
Conclusion = Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "NEEDS_TAX_REVIEW"]
Unknown = Literal[
    "MISSING_EVIDENCE",
    "MISSING_SIGNED_POD",
    "UNVERIFIED_SOURCE",
    "AMBIGUOUS_INVOICE",
    "UNKNOWN_CUSTOMER",
    "UNKNOWN_AMOUNT",
    "UNCERTAIN_EXTRACTION",
    "SEARCH_INCOMPLETE",
    "CONFLICTING_EVIDENCE",
    "PROVIDER_FAILURE",
    "BUDGET_EXHAUSTED",
    "STALE_INPUTS",
    "UNSUPPORTED_CLASSIFICATION",
    "FORGED_CITATION",
    "NEEDS_TAX_REVIEW",
]
Action = Literal["HUMAN_REVIEW", "REQUEST_EVIDENCE", "REFRESH_INPUTS", "TAX_REVIEW"]


class Limits(Strict):
    max_claims: Annotated[int, Field(strict=True, ge=1, le=20)] = 10
    max_rounds: Annotated[int, Field(strict=True, ge=1, le=32)] = 24
    max_tool_calls: Annotated[int, Field(strict=True, ge=0, le=128)] = 32
    max_input_tokens: Annotated[int, Field(strict=True, ge=0, le=1000000)] = 65536
    max_output_tokens: Annotated[int, Field(strict=True, ge=0, le=100000)] = 32768
    max_spend_paise: Annotated[int, Field(strict=True, ge=0, le=100000)] = 0
    timeout_ms: Annotated[int, Field(strict=True, ge=100, le=120000)] = 30000
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=3)] = 2


class StartInput(Strict):
    expected_case_version: Version
    expected_context_sha256: Hash
    claim_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)]
    allow_external: bool = False

    @model_validator(mode="after")
    def distinct(self) -> "StartInput":
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("Duplicate claim IDs")
        return self


class ResumeInput(Strict):
    expected_run_version: Version


class Objective(Strict):
    claim_id: UUID
    claim_version: int
    category: Category
    amount_paise: int | None
    basis_sha256: Hash
    invoice_id: UUID | None
    question: Question
    tools: list[Tool]
    unknowns: list[Unknown]


class OfferedPointer(Strict):
    record_id: UUID
    document_id: UUID
    document_version: int
    raw_sha256: Hash
    canonical_sha256: Hash
    page: int
    start: int
    end: int
    excerpt: Annotated[str, Field(min_length=1, max_length=2000)]


class Proposal(Strict):
    classification: Category
    suggested_state: Conclusion
    citations: Annotated[list[OfferedPointer], Field(max_length=20)]
    unknowns: Annotated[list[Unknown], Field(max_length=15)]
    inference: Literal["PREDICATE_MAY_APPLY", "POSSIBLE_CONTRADICTION", "NO_BACKED_CONCLUSION"]
    next_action: Action
    financial_authority: Literal[False] = False


class InvestigatorReply(Strict):
    action: Literal["SEARCH", "HYPOTHESIS"]
    tool: Tool | None = None
    proposal: Proposal | None = None

    @model_validator(mode="after")
    def shape(self) -> "InvestigatorReply":
        if (self.action == "SEARCH") != (self.tool is not None):
            raise ValueError("Tool request mismatch")
        if (self.action == "HYPOTHESIS") != (self.proposal is not None):
            raise ValueError("Hypothesis request mismatch")
        return self


class ProviderInput(Strict):
    objective: Objective
    hits: Annotated[list[Hit], Field(max_length=50)]
    offered: Annotated[list[OfferedPointer], Field(max_length=20)]
    searched_tools: list[Tool]


class Finding(Strict):
    claim_id: UUID
    classification: Category
    state: Conclusion
    source_facts: list[Verification]
    citations: list[OfferedPointer]
    inference: Literal["PREDICATE_MAY_APPLY", "POSSIBLE_CONTRADICTION", "NO_BACKED_CONCLUSION"]
    contradictions: list[str]
    unknowns: list[Unknown]
    next_action: Action
    algorithm: Literal["director-investigator-v1"] = "director-investigator-v1"
    requires_human_review: Literal[True] = True
    financial_authority: Literal[False] = False


class Frame(Strict):
    objectives: list[Objective] = Field(default_factory=list)
    index: int = 0
    rounds: int = 0
    hits: list[Hit] = Field(default_factory=list)
    offered: list[OfferedPointer] = Field(default_factory=list)
    searched_tools: list[Tool] = Field(default_factory=list)
    proposal: Proposal | None = None
    verification: Verification | None = None
    findings: list[Finding] = Field(default_factory=list)
    error_code: str | None = None
    incomplete: bool = False
    finished: bool = False


class FindingView(Finding):
    is_current: bool


class RunView(Strict):
    id: UUID
    case_id: UUID
    version: int
    status: str
    recommendation: Literal["AWAITING_REVIEW", "AWAITING_EVIDENCE"]
    source_case_version: int
    result_case_version: int | None
    input_sha256: str
    provider: str
    is_stale: bool
    claim_ids: list[UUID]
    tool_calls: int
    provider_attempts: int
    reserved_input_tokens: int
    reserved_output_tokens: int
    reserved_cost_paise: int
    error_code: str | None
    financial_authority: Literal[False] = False
