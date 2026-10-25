"""Case workflow is metadata, never permission to settle or adjudicate money."""

from enum import StrEnum

MAX_PAISE = 2**63 - 1


class CaseState(StrEnum):
    NEW = "NEW"
    MATCHING = "MATCHING"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    READY_TO_APPLY = "READY_TO_APPLY"
    PARTIALLY_SETTLED = "PARTIALLY_SETTLED"
    CLOSED = "CLOSED"


class ClaimState(StrEnum):
    EXTRACTED = "EXTRACTED"
    INVESTIGATING = "INVESTIGATING"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NEEDS_TAX_REVIEW = "NEEDS_TAX_REVIEW"
    ACCEPTED = "ACCEPTED"
    DISPUTED = "DISPUTED"
    AWAITING_CUSTOMER_EVIDENCE = "AWAITING_CUSTOMER_EVIDENCE"
    RESOLVED = "RESOLVED"


CASE_EDGES: dict[CaseState, set[CaseState]] = {
    CaseState.NEW: {CaseState.MATCHING},
    CaseState.MATCHING: {
        CaseState.INVESTIGATING,
        CaseState.AWAITING_EVIDENCE,
        CaseState.AWAITING_REVIEW,
    },
    CaseState.INVESTIGATING: {
        CaseState.AWAITING_EVIDENCE,
        CaseState.AWAITING_REVIEW,
        CaseState.READY_TO_APPLY,
    },
    CaseState.AWAITING_EVIDENCE: {CaseState.INVESTIGATING},
    CaseState.AWAITING_REVIEW: {CaseState.INVESTIGATING, CaseState.READY_TO_APPLY},
    CaseState.READY_TO_APPLY: {
        CaseState.INVESTIGATING,
        CaseState.PARTIALLY_SETTLED,
        CaseState.CLOSED,
    },
    CaseState.PARTIALLY_SETTLED: {
        CaseState.INVESTIGATING,
        CaseState.AWAITING_REVIEW,
        CaseState.CLOSED,
    },
    CaseState.CLOSED: {CaseState.INVESTIGATING},
}
ASSESSMENTS = {
    ClaimState.SUPPORTED,
    ClaimState.CONTRADICTED,
    ClaimState.INSUFFICIENT_EVIDENCE,
    ClaimState.NEEDS_TAX_REVIEW,
}
DECISIONS = {ClaimState.ACCEPTED, ClaimState.DISPUTED, ClaimState.AWAITING_CUSTOMER_EVIDENCE}
CLAIM_EDGES: dict[ClaimState, set[ClaimState]] = {
    ClaimState.EXTRACTED: {ClaimState.INVESTIGATING},
    ClaimState.INVESTIGATING: ASSESSMENTS,
    **{state: DECISIONS | {ClaimState.INVESTIGATING} for state in ASSESSMENTS},
    **{state: {ClaimState.RESOLVED, ClaimState.INVESTIGATING} for state in DECISIONS},
    ClaimState.RESOLVED: {ClaimState.INVESTIGATING},
}


class CaseError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def case_transition(current: CaseState, target: CaseState) -> None:
    if target not in CASE_EDGES[current]:
        raise CaseError("INVALID_CASE_TRANSITION")
    if target in {CaseState.READY_TO_APPLY, CaseState.PARTIALLY_SETTLED, CaseState.CLOSED}:
        raise CaseError("VALIDATED_SETTLEMENT_CAPABILITY_REQUIRED", 403)


def claim_transition(current: ClaimState, target: ClaimState, category: str) -> None:
    if target not in CLAIM_EDGES[current]:
        raise CaseError("INVALID_CLAIM_TRANSITION")
    if target in {
        ClaimState.SUPPORTED,
        ClaimState.CONTRADICTED,
        ClaimState.ACCEPTED,
        ClaimState.RESOLVED,
    }:
        raise CaseError("VALIDATED_ADJUDICATION_CAPABILITY_REQUIRED", 403)
    if category == "tax" and target in {ClaimState.DISPUTED}:
        raise CaseError("SPECIALIST_TAX_REVIEW_REQUIRED", 403)


def claimed_total(amounts: list[int | None]) -> tuple[int | None, int]:
    for amount in amounts:
        if amount is not None and (type(amount) is not int or not 0 <= amount <= MAX_PAISE):
            raise ValueError("Invalid claim paise")
    total = sum(amount for amount in amounts if amount is not None)
    return (total if total <= MAX_PAISE else None, sum(a is None for a in amounts))


def retry_seconds(attempt: int) -> int:
    if type(attempt) is not int or not 1 <= attempt <= 10:
        raise ValueError("Invalid attempt")
    return min(60, 1 << (attempt - 1))
