from decimal import Decimal

import pytest

from liquidity_forecaster.money import format_nok, parse_decimal


def test_parse_decimal_from_string() -> None:
    assert parse_decimal("1000.00") == Decimal("1000.00")


def test_parse_decimal_rejects_float() -> None:
    with pytest.raises(TypeError):
        parse_decimal(1000.0)


def test_format_nok_groups_thousands() -> None:
    assert format_nok(Decimal("250000.00")) == "250 000 NOK"
    assert format_nok(Decimal("-5000.00")) == "-5 000 NOK"
    assert format_nok(Decimal("90000.50")) == "90 000.50 NOK"
