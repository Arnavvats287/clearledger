"""Pure deterministic single-invoice proposals. No persistence or balance mutation."""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

Outcome = Literal["EXACT_MATCH", "AMBIGUOUS", "NO_SUPPORTED_MATCH"]
Identity = Literal["RESOLVED", "AMBIGUOUS", "UNRESOLVED"]


def invoice_reference_span(value: str, start: int, end: int, quote: str) -> bool:
    """An exact reference cannot be a prefix/suffix of another identifier."""

    def identifier_character(character: str) -> bool:
        return character.isalnum() or character in "-_./"

    return (
        0 <= start < end <= len(value)
        and value[start:end] == quote
        and (start == 0 or not identifier_character(value[start - 1]))
        and (end == len(value) or not identifier_character(value[end]))
    )


def integer(value: int, *, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError("Financial values/versions must be integers, never floats or booleans")
    if not minimum <= value <= 2**63 - 1:
        raise ValueError("Financial value/version out of range")


@dataclass(frozen=True)
class InvoiceState:
    id: UUID
    customer_id: UUID
    version: int
    open_paise: int
    status: str
    issued_date: date
    currency: str = "INR"

    def __post_init__(self) -> None:
        integer(self.version, minimum=1)
        integer(self.open_paise)


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    identity: Identity
    customers: tuple[UUID, ...]
    candidates: tuple[UUID, ...]
    invoice_id: UUID | None = None
    invoice_version: int | None = None
    amount_paise: int = 0


def decide(
    *,
    unapplied_paise: int,
    receipt_status: str,
    receipt_date: date,
    customers: tuple[UUID, ...],
    references: tuple[UUID, ...],
    invoices: tuple[InvoiceState, ...],
    stale_evidence: bool = False,
    budget_exceeded: bool = False,
) -> Decision:
    integer(unapplied_paise)
    owners = tuple(sorted(set(customers), key=str))
    identity: Identity = "RESOLVED" if len(owners) == 1 else "AMBIGUOUS" if owners else "UNRESOLVED"
    eligible = tuple(
        sorted(
            (
                invoice.id
                for invoice in invoices
                if invoice.customer_id in owners
                and invoice.status == "OPEN"
                and invoice.currency == "INR"
                and invoice.open_paise > 0
                and invoice.open_paise == unapplied_paise
                and invoice.issued_date <= receipt_date
            ),
            key=str,
        )
    )

    def abstain(reason: str, ambiguous: bool = False) -> Decision:
        return Decision(
            "AMBIGUOUS" if ambiguous else "NO_SUPPORTED_MATCH", reason, identity, owners, eligible
        )

    if budget_exceeded:
        return abstain("AMBIGUOUS_OR_BUDGET_EXCEEDED", True)
    if stale_evidence:
        return abstain("STALE_OR_INVALID_EVIDENCE")
    if receipt_status not in ("UNAPPLIED", "PARTIALLY_APPLIED") or unapplied_paise == 0:
        return abstain("NO_AVAILABLE_CASH")
    if len(owners) > 1:
        return abstain("CONFLICTING_CUSTOMER_EVIDENCE", True)
    if not owners:
        return abstain("UNRESOLVED_CUSTOMER")
    targets = tuple(sorted(set(references), key=str))
    if len(targets) > 1:
        return abstain("CONFLICTING_INVOICE_REFERENCES", True)
    if not targets:
        return abstain(
            "MULTIPLE_EXACT_INVOICES"
            if len(eligible) > 1
            else "VERIFIED_INVOICE_REFERENCE_REQUIRED",
            len(eligible) > 1,
        )
    target = next((invoice for invoice in invoices if invoice.id == targets[0]), None)
    if target is None or target.customer_id != owners[0]:
        return abstain("INVOICE_CUSTOMER_MISMATCH")
    if target.currency != "INR":
        return abstain("UNSUPPORTED_CURRENCY")
    if target.status != "OPEN" or target.open_paise == 0:
        return abstain("INVOICE_NOT_OPEN")
    if target.issued_date > receipt_date:
        return abstain("INVOICE_NOT_ISSUED_AT_RECEIPT")
    if target.open_paise != unapplied_paise:
        return abstain("AMOUNT_NOT_EXACT")
    return Decision(
        "EXACT_MATCH",
        "VERIFIED_REFERENCE_AND_EXACT_OPEN_BALANCE",
        identity,
        owners,
        eligible,
        target.id,
        target.version,
        unapplied_paise,
    )
