"""Acceptance tests AC-1..AC-5 against the worked example."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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


def _accounts_with_two_operational():
    payload = fixtures.accounts_response()
    second = dict(payload["accounts"][0])
    second["accountNumber"] = "36060000009"
    second["name"] = "Drift 2"
    payload["accounts"].append(second)
    return AccountsResponse.model_validate(payload).accounts


def test_multiple_operational_requires_or_selects() -> None:
    accounts = _accounts_with_two_operational()
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    # Unconfigured: deterministic pick (lowest account number) — does not crash.
    f = build_forecast(accounts, payments, Config(), today=fixtures.TODAY)
    assert f.operational_account == fixtures.OPERATIONAL_ACCOUNT
    # Configured: the chosen account wins (no scheduled items hit it → stays flat).
    cfg = Config(operational_account="36060000009")
    f2 = build_forecast(accounts, payments, cfg, today=fixtures.TODAY)
    assert f2.operational_account == "36060000009"
    assert f2.items == []


def test_no_operational_account_raises() -> None:
    payload = fixtures.accounts_response()
    payload["accounts"] = [a for a in payload["accounts"] if a["type"] != "Operational"]
    accounts = AccountsResponse.model_validate(payload).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    with pytest.raises(ValueError, match="Operational"):
        build_forecast(accounts, payments, Config(), today=fixtures.TODAY)


def test_configured_operational_account_missing_raises() -> None:
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    with pytest.raises(ValueError, match="not found"):
        build_forecast(
            accounts, payments, Config(operational_account="does-not-exist"), today=fixtures.TODAY
        )


def test_non_nok_payment_sets_fx_flag() -> None:
    payload = fixtures.payments_response()
    payload["payments"].append(
        {
            "id": "fx1",
            "eventId": "fx1",
            "createdAt": "2026-06-01T08:00:00Z",
            "createdByAgentId": "00000000-0000-0000-0000-000000000000",
            "state": "InProcess",
            "creditor": {"name": "EU Vendor", "accountNumber": "9999999999"},
            "debtorAccountNumber": fixtures.OPERATIONAL_ACCOUNT,
            "currencyAmount": {"amount": "5000.00", "currency": "EUR"},
            "executionDate": "2026-06-20",
        }
    )
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payments = PaymentsResponse.model_validate(payload).payments
    f = build_forecast(accounts, payments, Config(), today=fixtures.TODAY)
    assert f.fx_variable is True
