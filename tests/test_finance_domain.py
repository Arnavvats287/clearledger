"""Independent integer-money, double-entry and authorization invariants."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from clearledger.finance_contract import Cash, Chart, Journal, Line, PolicyInput, Treatment
from clearledger.finance_domain import balanced, compose, transition
from clearledger.finance_identity import Principal


@given(
    st.lists(st.integers(min_value=1, max_value=1000000), min_size=1, max_size=10),
    st.integers(min_value=0, max_value=1000000),
    st.booleans(),
)
def test_double_entry_and_cash_conservation_oracle(amounts, left, recognized):
    allocations = [Cash(invoice_id=uuid4(), amount_paise=amount) for amount in amounts]
    original = sum(amounts) + left
    journals = compose(Chart(), original, allocations, [], recognized)
    movement = {}
    for journal in journals:
        assert sum(line.debit_paise for line in journal.lines) == sum(
            line.credit_paise for line in journal.lines
        )
        for line in journal.lines:
            movement[line.account_role] = (
                movement.get(line.account_role, 0) + line.debit_paise - line.credit_paise
            )
    assert movement["AR"] == -sum(amounts)
    assert movement["UNAPPLIED"] == (sum(amounts) if recognized else -left)
    assert movement.get("BANK", 0) == (0 if recognized else original)
    assert sum(movement.values()) == 0


@given(st.integers(min_value=1, max_value=1000000), st.integers(min_value=1, max_value=1000000))
def test_noncash_does_not_consume_receipt_or_hide_open_ar(cash, withholding):
    invoice, claim = uuid4(), uuid4()
    treatment = Treatment(
        claim_id=claim,
        invoice_id=invoice,
        category="tax",
        amount_paise=withholding,
        allowed_paise=withholding,
        state="SUPPORTED",
        rule_id="isolated-fixture",
        treatment="INCOME_TAX",
        evidence_ids=[uuid4()],
        reasons=["REVIEWED_SYNTHETIC_POLICY_ONLY"],
    )
    journals = compose(
        Chart(), cash, [Cash(invoice_id=invoice, amount_paise=cash)], [treatment], False
    )
    application = journals[-1]
    assert (
        next(line.debit_paise for line in application.lines if line.account_role == "UNAPPLIED")
        == cash
    )
    assert (
        next(line.credit_paise for line in application.lines if line.account_role == "AR")
        == cash + withholding
    )
    gross = cash + withholding + 250000
    assert gross - sum(line.credit_paise for line in application.lines) == 250000


@pytest.mark.parametrize("amount", [0, -1, 0.5, 100.0, True, "100", 2**63])
def test_non_integer_or_invalid_paise_rejected(amount):
    with pytest.raises(ValidationError):
        Cash(invoice_id=uuid4(), amount_paise=amount)


@pytest.mark.parametrize("error", ["unbalanced", "both", "account", "boolean", "overflow"])
def test_balance_validator_is_strict(error):
    chart = Chart()
    debit = Line(account_role="BANK", account_code="1010", debit_paise=100)
    credit = Line(account_role="UNAPPLIED", account_code="2300", credit_paise=100)
    if error == "unbalanced":
        debit = debit.model_copy(update={"debit_paise": 99})
    elif error == "both":
        debit = debit.model_copy(update={"credit_paise": 100})
    elif error == "account":
        debit = debit.model_copy(update={"account_code": "2110"})
    elif error == "boolean":
        debit = debit.model_copy(update={"debit_paise": True})
    else:
        debit = debit.model_copy(update={"debit_paise": 2**63})
    with pytest.raises((ValueError, TypeError)):
        balanced(Journal(kind="BANK", lines=[debit, credit]), chart)


@pytest.mark.parametrize("target", ["APPROVED", "SIMULATED_POSTED", "REJECTED"])
def test_financial_state_cannot_jump_from_draft(target):
    with pytest.raises(ValueError):
        transition("DRAFT", target)


def test_no_self_altering_approval_or_output_gst_policy():
    with pytest.raises(ValidationError):
        PolicyInput(
            reference="test",
            version=1,
            effective_from="2026-01-01",
            effective_to="2026-12-31",
            require_maker_checker=False,
        )
    with pytest.raises(ValidationError):
        Chart(ALLOWANCE="2110")
    with pytest.raises(ValidationError):
        Chart(AR="1010")


@pytest.mark.parametrize("fault", ["expired", "future", "foreign", "permission", "service"])
def test_identity_authority_rejects_invalid_claims(fault):
    org = uuid4()
    now = datetime.now(UTC)
    principal = Principal(
        issuer="isolated-unit-issuer",
        subject=uuid4(),
        organization_id=org,
        authorization_version="1",
        permissions=frozenset({"APPROVE"}),
        authenticated_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=1),
    )
    if fault == "expired":
        principal = principal.model_copy(update={"expires_at": now - timedelta(seconds=1)})
    elif fault == "future":
        principal = principal.model_copy(update={"authenticated_at": now + timedelta(minutes=1)})
    elif fault == "foreign":
        org = uuid4()
    elif fault == "permission":
        principal = principal.model_copy(update={"permissions": frozenset()})
    else:
        principal = principal.model_copy(update={"service": True})
    with pytest.raises(HTTPException):
        principal.require("APPROVE", org)
