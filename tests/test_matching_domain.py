from datetime import date
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clearledger.matching_domain import InvoiceState, decide, invoice_reference_span

C = UUID(int=1)
INVOICE_ID = UUID(int=2)


def decision(amount=100, **changes):
    args = dict(
        unapplied_paise=amount,
        receipt_status="UNAPPLIED",
        receipt_date=date(2026, 1, 2),
        customers=(C,),
        references=(INVOICE_ID,),
        invoices=(InvoiceState(INVOICE_ID, C, 1, amount, "OPEN", date(2026, 1, 1)),),
    )
    args.update(changes)
    return decide(**args)


def test_exact_reference_required_and_identity_is_separate():
    assert decision().outcome == "EXACT_MATCH"
    assert decision(references=()).outcome == "NO_SUPPORTED_MATCH"
    assert decision(customers=(), references=()).identity == "UNRESOLVED"
    assert decision(customers=(C, UUID(int=3))).outcome == "AMBIGUOUS"
    assert decision(references=(INVOICE_ID, UUID(int=4))).reason == "CONFLICTING_INVOICE_REFERENCES"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"unapplied_paise": 0}, "NO_AVAILABLE_CASH"),
        ({"receipt_status": "FULLY_APPLIED"}, "NO_AVAILABLE_CASH"),
        ({"stale_evidence": True}, "STALE_OR_INVALID_EVIDENCE"),
        ({"budget_exceeded": True}, "AMBIGUOUS_OR_BUDGET_EXCEEDED"),
        ({"invoices": ()}, "INVOICE_CUSTOMER_MISMATCH"),
        (
            {"invoices": (InvoiceState(INVOICE_ID, C, 1, 0, "CLOSED", date(2026, 1, 1)),)},
            "INVOICE_NOT_OPEN",
        ),
        (
            {"invoices": (InvoiceState(INVOICE_ID, C, 1, 99, "OPEN", date(2026, 1, 1)),)},
            "AMOUNT_NOT_EXACT",
        ),
        (
            {"invoices": (InvoiceState(INVOICE_ID, C, 1, 100, "OPEN", date(2027, 1, 1)),)},
            "INVOICE_NOT_ISSUED_AT_RECEIPT",
        ),
        (
            {"invoices": (InvoiceState(INVOICE_ID, C, 1, 100, "OPEN", date(2026, 1, 1), "USD"),)},
            "UNSUPPORTED_CURRENCY",
        ),
    ],
)
def test_abstention(change, reason):
    result = decision(**change)
    assert result.reason == reason
    assert result.amount_paise == 0
    assert result.invoice_id is None


def test_multiple_equal_invoices_are_ambiguous_without_reference():
    result = decision(
        references=(),
        invoices=(
            InvoiceState(INVOICE_ID, C, 1, 100, "OPEN", date(2026, 1, 1)),
            InvoiceState(UUID(int=3), C, 1, 100, "OPEN", date(2026, 1, 1)),
        ),
    )
    assert result.outcome == "AMBIGUOUS"
    assert result.candidates == (INVOICE_ID, UUID(int=3))


@pytest.mark.parametrize("value", [100.0, True, -1, 2**63])
def test_invalid_money_fails(value):
    with pytest.raises((TypeError, ValueError)):
        decision(unapplied_paise=value)


@given(st.integers(min_value=1, max_value=2**63 - 1))
def test_exact_paise_conservation_without_mutation(amount):
    invoice = InvoiceState(INVOICE_ID, C, 7, amount, "OPEN", date(2026, 1, 1))
    result = decision(amount=amount, invoices=(invoice,))
    assert result.amount_paise == amount
    assert result.invoice_version == 7
    assert invoice.open_paise == amount


@pytest.mark.parametrize(
    "text,start,end,quote,valid",
    [
        ("INV-10", 0, 5, "INV-1", False),
        ("XINV-1", 1, 6, "INV-1", False),
        ("INV-1/2", 0, 5, "INV-1", False),
        ("Invoice: INV-1;", 9, 14, "INV-1", True),
        ("INV-1", 0, 6, "INV-1", False),
    ],
)
def test_complete_reference_token(text, start, end, quote, valid):
    assert invoice_reference_span(text, start, end, quote) is valid
