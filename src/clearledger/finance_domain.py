"""Exact double entry and explicit proposal transitions; no framework or I/O."""

from uuid import UUID

from clearledger.finance_contract import Cash, Chart, Journal, Line, Treatment
from clearledger.matching_domain import integer

ALGORITHM = "accounting-simulator-v1"
EDGES: dict[str, set[str]] = {
    "DRAFT": {"VALIDATED", "INVALIDATED"},
    "VALIDATED": {"PENDING_APPROVAL", "INVALIDATED"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "INVALIDATED"},
    "APPROVED": {"SIMULATED_POSTED", "INVALIDATED"},
    "REJECTED": set(),
    "SIMULATED_POSTED": set(),
    "INVALIDATED": set(),
}


def transition(before: str, after: str) -> None:
    if after not in EDGES.get(before, set()):
        raise ValueError("Invalid journal proposal transition")


def balanced(journal: Journal, chart: Chart) -> None:
    debit = credit = 0
    for line in journal.lines:
        integer(line.debit_paise)
        integer(line.credit_paise)
        if chart.model_dump()[line.account_role] != line.account_code:
            raise ValueError("Account outside reviewed chart")
        if (line.debit_paise > 0) == (line.credit_paise > 0):
            raise ValueError("Invalid journal line")
        debit += line.debit_paise
        credit += line.credit_paise
    integer(debit, minimum=1)
    integer(credit, minimum=1)
    if debit != credit:
        raise ValueError("Unbalanced journal")


def compose(
    chart: Chart,
    receipt_amount: int,
    cash: list[Cash],
    treatments: list[Treatment],
    recognized: bool,
) -> list[Journal]:
    integer(receipt_amount, minimum=1)
    totals: dict[UUID, int] = {}
    cash_total = 0
    for allocation in cash:
        if allocation.invoice_id in totals:
            raise ValueError("Duplicate allocation target")
        integer(allocation.amount_paise, minimum=1)
        totals[allocation.invoice_id] = allocation.amount_paise
        cash_total += allocation.amount_paise
    integer(cash_total, minimum=1)
    if cash_total > receipt_amount:
        raise ValueError("Receipt over-allocation")
    lines = [Line(account_role="UNAPPLIED", account_code=chart.UNAPPLIED, debit_paise=cash_total)]
    for treatment in treatments:
        if not treatment.allowed_paise:
            continue
        if (
            treatment.state != "SUPPORTED"
            or treatment.treatment is None
            or not treatment.evidence_ids
        ):
            raise ValueError("Unsupported noncash treatment")
        if treatment.invoice_id not in totals:
            raise ValueError("Noncash target outside application")
        totals[treatment.invoice_id] += treatment.allowed_paise
        lines.append(
            Line(
                account_role=treatment.treatment,
                account_code=chart.model_dump()[treatment.treatment],
                debit_paise=treatment.allowed_paise,
                invoice_id=treatment.invoice_id,
            )
        )
    lines.extend(
        Line(account_role="AR", account_code=chart.AR, credit_paise=amount, invoice_id=invoice_id)
        for invoice_id, amount in sorted(totals.items())
    )
    journals = []
    if not recognized:
        journals.append(
            Journal(
                kind="BANK",
                lines=[
                    Line(account_role="BANK", account_code=chart.BANK, debit_paise=receipt_amount),
                    Line(
                        account_role="UNAPPLIED",
                        account_code=chart.UNAPPLIED,
                        credit_paise=receipt_amount,
                    ),
                ],
            )
        )
    journals.append(Journal(kind="APPLICATION", lines=lines))
    for journal in journals:
        balanced(journal, chart)
    return journals
