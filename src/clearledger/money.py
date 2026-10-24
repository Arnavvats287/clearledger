"""Signed integer paise; ROUND_HALF_UP only at explicit conversion boundaries.

Decimal strings use plain base-10 notation without whitespace or exponents.
Rates are multipliers (0.025 means 2.5%); percentages are percent units (2.5).
"""

import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

_DECIMAL_STRING = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def _decimal(value: str | Decimal) -> Decimal:
    if isinstance(value, str):
        if not _DECIMAL_STRING.fullmatch(value):
            raise ValueError("Expected a plain decimal string")
        result = Decimal(value)
    elif isinstance(value, Decimal):
        result = value
    else:
        raise TypeError("Expected str or Decimal; floats are forbidden")
    if not result.is_finite():
        raise ValueError("Money and rates must be finite")
    return result


def _integer(value: int) -> None:
    if type(value) is not int:
        raise TypeError("Paise must be an integer; floats and bools are forbidden")


def paise_from_decimal_string(value: str) -> int:
    if not isinstance(value, str):
        raise TypeError("Expected a decimal string; floats are forbidden")
    amount = _decimal(value)
    with localcontext() as ctx:
        ctx.prec = max(28, len(amount.as_tuple().digits) + 3)
        return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def decimal_string_from_paise(value: int) -> str:
    _integer(value)
    whole, fraction = divmod(abs(value), 100)
    return f"{'-' if value < 0 else ''}{whole}.{fraction:02d}"


def multiply_paise_by_rate(amount_paise: int, rate: str | Decimal) -> int:
    """Round the resulting paise once, with ties away from zero."""
    _integer(amount_paise)
    multiplier = _decimal(rate)
    with localcontext() as ctx:
        ctx.prec = max(
            28,
            len(str(abs(amount_paise)))
            + len(multiplier.as_tuple().digits)
            + abs(multiplier.adjusted())
            + 3,
        )
        return int(
            (Decimal(amount_paise) * multiplier).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )


def percentage_of_paise(amount_paise: int, percentage: str | Decimal) -> int:
    percent = _decimal(percentage)
    with localcontext() as ctx:
        ctx.prec = max(28, len(percent.as_tuple().digits) + 3)
        return multiply_paise_by_rate(amount_paise, percent / Decimal(100))
