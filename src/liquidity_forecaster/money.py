"""Money handling. All amounts are fixed-point ``Decimal`` — never float.

Folio returns amounts as decimal strings (e.g. ``"1000.00"``). We parse them
defensively and keep two-decimal precision for NOK.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final

CENTS: Final = Decimal("0.01")


def parse_decimal(value: str | int | float | Decimal) -> Decimal:
    """Parse a Folio money string into a ``Decimal``.

    Accepts the documented decimal-string form. ``float`` is rejected to avoid
    silently importing binary-floating-point error into money math.
    """
    if isinstance(value, float):
        raise TypeError("refusing to build money from float; pass a string")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"invalid decimal amount: {value!r}") from exc


def quantize(amount: Decimal) -> Decimal:
    """Round to two decimal places (NOK øre)."""
    return amount.quantize(CENTS)


def format_nok(amount: Decimal) -> str:
    """Human-friendly NOK formatting, e.g. ``250000.00`` -> ``250 000 NOK``."""
    q = quantize(amount)
    sign = "-" if q < 0 else ""
    whole, frac = divmod(abs(q), Decimal(1))
    grouped = f"{int(whole):,}".replace(",", " ")
    if frac == 0:
        return f"{sign}{grouped} NOK"
    return f"{sign}{grouped}.{int(frac * 100):02d} NOK"
