from decimal import Decimal, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clearledger.money import (
    decimal_string_from_paise,
    multiply_paise_by_rate,
    paise_from_decimal_string,
    percentage_of_paise,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.005", 101),
        ("0.01", 1),
        ("0", 0),
        ("-0.005", -1),
        ("-1.005", -101),
        ("+12.30", 1230),
        ("0.0049", 0),
        ("999999999999999999999999999999.995", 100000000000000000000000000000000),
    ],
)
def test_conversion(value, expected):
    assert paise_from_decimal_string(value) == expected


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e3", "", " 1.00", "1,000", "1.2.3"])
def test_invalid_string(value):
    with pytest.raises(ValueError):
        paise_from_decimal_string(value)


@pytest.mark.parametrize("value", [1.005, 1, True, None, Decimal("1")])
def test_conversion_requires_string(value):
    with pytest.raises(TypeError):
        paise_from_decimal_string(value)


@pytest.mark.parametrize("value", [1.0, True, "100", Decimal(100)])
def test_integer_inputs_reject_other_types(value):
    for operation in (
        lambda: decimal_string_from_paise(value),
        lambda: multiply_paise_by_rate(value, "1"),
        lambda: percentage_of_paise(value, "1"),
    ):
        with pytest.raises(TypeError):
            operation()


@pytest.mark.parametrize("operation", [multiply_paise_by_rate, percentage_of_paise])
def test_rate_rejects_float_and_nonfinite(operation):
    with pytest.raises(TypeError):
        operation(100, 0.5)
    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(ValueError):
            operation(100, value)


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [(101, "0.5", 51), (-101, "0.5", -51), (101, "-0.5", -51), (0, "0.5", 0)],
)
def test_rate_rounding(amount, rate, expected):
    assert multiply_paise_by_rate(amount, rate) == expected
    assert multiply_paise_by_rate(amount, Decimal(rate)) == expected


def test_percentage_and_context_independence():
    with localcontext() as ctx:
        ctx.prec = 3
        assert percentage_of_paise(10001, "2.5") == 250
        assert percentage_of_paise(-101, "50") == -51
        assert paise_from_decimal_string("1234567.895") == 123456790
        assert multiply_paise_by_rate(123456790, "1") == 123456790


@pytest.mark.parametrize(("amount", "expected"), [(0, "0.00"), (1, "0.01"), (-1, "-0.01")])
def test_display(amount, expected):
    assert decimal_string_from_paise(amount) == expected


@given(st.integers(min_value=-(10**60), max_value=10**60))
def test_signed_paise_roundtrip(amount):
    assert paise_from_decimal_string(decimal_string_from_paise(amount)) == amount


@given(st.integers(min_value=-(10**18), max_value=10**18))
def test_identity_and_zero_rate(amount):
    assert multiply_paise_by_rate(amount, "1") == amount
    assert multiply_paise_by_rate(amount, "0") == 0
    assert percentage_of_paise(amount, "100") == amount
