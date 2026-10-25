"""Strict simulation contract. No legal rule is inferred from an extracted claim."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, model_validator

from clearledger.document_contract import Category
from clearledger.evidence_contract import Hash, Strict
from clearledger.matching_schemas import Version

Paise = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
Positive = Annotated[int, Field(strict=True, ge=1, le=2**63 - 1)]
Code = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]
Account = Annotated[str, Field(pattern=r"^[0-9]{4,8}$")]
Role = Literal["BANK", "AR", "UNAPPLIED", "INCOME_TAX", "GST_TAX", "ALLOWANCE"]


def exact_date(value: object) -> object:
    if type(value) is date:
        return value
    if (
        isinstance(value, str)
        and len(value) == 10
        and date.fromisoformat(value).isoformat() == value
    ):
        return value
    raise ValueError("Expected YYYY-MM-DD")


FinanceDate = Annotated[date, BeforeValidator(exact_date)]


class Chart(Strict):
    BANK: Account = "1010"
    AR: Account = "1200"
    UNAPPLIED: Account = "2300"
    INCOME_TAX: Account = "1310"
    GST_TAX: Account = "1320"
    ALLOWANCE: Account = "4100"
    OUTPUT_GST: Account = "2110"

    @model_validator(mode="after")
    def distinct(self) -> "Chart":
        if len(set(self.model_dump().values())) != 7 or "2110" in {
            self.BANK,
            self.AR,
            self.UNAPPLIED,
            self.INCOME_TAX,
            self.GST_TAX,
            self.ALLOWANCE,
        }:
            raise ValueError("Distinct permitted accounts required; no output GST adjustment")
        return self


class Rule(Strict):
    id: Code
    version: Version = 1
    category: Category
    treatment: Literal["INCOME_TAX", "GST_TAX", "ALLOWANCE"]
    approved_fixture: Annotated[bool, Field(strict=True)] = False
    jurisdiction: Literal["IN-SIMULATION"] = "IN-SIMULATION"
    provision: Literal["SYNTHETIC_STIPULATION"] = "SYNTHETIC_STIPULATION"
    transaction_category: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    basis: Literal["STIPULATED_AMOUNT"] = "STIPULATED_AMOUNT"
    rate_bps: None = None
    threshold_paise: None = None
    source_url: None = None
    effective_from: FinanceDate
    effective_to: FinanceDate
    date_of_deduction: FinanceDate | None = None
    case_id: UUID
    customer_id: UUID
    receipt_id: UUID
    invoice_id: UUID
    claim_id: UUID
    amount_paise: Positive
    required_evidence: Annotated[list[UUID], Field(min_length=1, max_length=20)]
    eligibility_preconditions: Literal["EXACT_REVIEWED_FIXTURE_SCOPE"] = (
        "EXACT_REVIEWED_FIXTURE_SCOPE"
    )
    recognition_policy: Literal["REVIEWED_NONCASH_RECEIVABLE", "REVIEWED_SALES_ALLOWANCE"]

    @model_validator(mode="after")
    def consistency(self) -> "Rule":
        if self.effective_to < self.effective_from or len(set(self.required_evidence)) != len(
            self.required_evidence
        ):
            raise ValueError("Invalid rule dates/evidence")
        if (self.category == "tax") != (self.treatment in {"INCOME_TAX", "GST_TAX"}):
            raise ValueError("Tax and commercial treatments are distinct")
        if self.category == "tax" and (
            self.date_of_deduction is None
            or self.recognition_policy != "REVIEWED_NONCASH_RECEIVABLE"
        ):
            raise ValueError("Explicit tax recognition/date policy required")
        if self.category != "tax" and self.recognition_policy != "REVIEWED_SALES_ALLOWANCE":
            raise ValueError("Separate allowance authorization required")
        return self


class PolicyInput(Strict):
    reference: Code
    version: Version
    previous_id: UUID | None = None
    enabled: Annotated[bool, Field(strict=True)] = True
    effective_from: FinanceDate
    effective_to: FinanceDate
    chart: Chart = Field(default_factory=Chart)
    require_controller_approval: Literal[True] = True
    require_maker_checker: Literal[True] = True
    max_cash_paise: Positive = 2**63 - 1
    max_noncash_paise: Paise = 2**63 - 1
    approval_ttl_seconds: Annotated[int, Field(strict=True, ge=1, le=3600)] = 900
    rules: Annotated[list[Rule], Field(max_length=20)] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistency(self) -> "PolicyInput":
        if self.effective_to < self.effective_from or len({r.id for r in self.rules}) != len(
            self.rules
        ):
            raise ValueError("Invalid policy")
        if (self.version == 1) != (self.previous_id is None):
            raise ValueError("A contiguous predecessor is required")
        return self


class Cash(Strict):
    invoice_id: UUID
    amount_paise: Positive


class ClaimTreatment(Strict):
    claim_id: UUID
    invoice_id: UUID
    rule_id: Code | None = None
    finding_id: UUID | None = None


class SourceReviewInput(Strict):
    expected_case_version: Version
    expected_context_sha256: Hash
    matching_proposal_id: UUID
    cash: Annotated[list[Cash], Field(min_length=1, max_length=20)]


class ProposalInput(SourceReviewInput):
    policy_id: UUID
    source_review_id: UUID
    claims: Annotated[list[ClaimTreatment], Field(max_length=20)] = Field(default_factory=list)


class CommandInput(Strict):
    expected_version: Version
    expected_snapshot_sha256: Hash


class ApprovalInput(CommandInput):
    decision: Literal["APPROVE", "REJECT"]
    reason: Literal["VERIFIED_SIMULATION", "INSUFFICIENT_EVIDENCE", "POLICY_NOT_MET"]


class Line(Strict):
    account_role: Role
    account_code: Account
    debit_paise: Paise = 0
    credit_paise: Paise = 0
    invoice_id: UUID | None = None

    @model_validator(mode="after")
    def one_side(self) -> "Line":
        if (self.debit_paise > 0) == (self.credit_paise > 0):
            raise ValueError("Exactly one positive side required")
        return self


class Journal(Strict):
    kind: Literal["BANK", "APPLICATION"]
    lines: Annotated[list[Line], Field(min_length=2, max_length=64)]


class Treatment(Strict):
    claim_id: UUID
    invoice_id: UUID
    category: Category
    amount_paise: Paise | None
    allowed_paise: Paise
    state: Literal["SUPPORTED", "NEEDS_TAX_REVIEW", "INSUFFICIENT_EVIDENCE"]
    rule_id: Code | None
    treatment: Literal["INCOME_TAX", "GST_TAX", "ALLOWANCE"] | None
    evidence_ids: list[UUID]
    reasons: list[str]
    legal_authority: Literal[False] = False


class ProposalView(Strict):
    id: UUID
    case_id: UUID
    receipt_id: UUID
    policy_id: UUID
    version: int
    state: str
    snapshot_sha256: str
    journals: list[Journal]
    treatments: list[Treatment]
    is_stale: bool
    simulation_only: Literal[True] = True
