"""Acceptance tests AC-1..AC-5 against the worked example."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from liquidity_forecaster.config import Config
from liquidity_forecaster.forecast import Severity, build_forecast
from liquidity_forecaster.models import AccountsResponse, PaymentsResponse

from . import fixtures


def _build(include_drafts: bool = False):
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    return build_forecast(
        accounts, payments, Config(), today=fixtures.TODAY, include_drafts=include_drafts
    )


def test_ac1_trough_matches_worked_example() -> None:
    f = _build()
    assert f.trough_date == date(2026, 6, 25)
    assert f.trough_balance == Decimal("90000.00")


def test_ac2_completed_excluded_inprocess_included() -> None:
    f = _build()
    creditors = {i.creditor for i in f.items}
    assert "Payroll" in creditors  # InProcess counted
    assert "Catering" not in creditors  # Completed excluded (already in balance)


def test_ac3_draft_toggle_lowers_trough() -> None:
    committed = _build(include_drafts=False)
    drafts = _build(include_drafts=True)
    assert committed.trough_balance == Decimal("90000.00")
    # Adding the 95 000 employer-tax Draft on 2026-06-25 pushes the trough negative.
    assert drafts.trough_balance == Decimal("-5000.00")


def test_ac5_amounts_are_decimal() -> None:
    f = _build()
    assert all(isinstance(i.amount, Decimal) for i in f.items)
    assert all(isinstance(b, Decimal) for _, b in f.curve)


def test_inflow_refund_raises_balance_after_trough() -> None:
    f = _build()
    by_date = dict(f.curve)
    assert by_date[date(2026, 7, 10)] == Decimal("210000.00")


def test_severity_red_when_below_floor() -> None:
    assert _build().severity is Severity.RED
