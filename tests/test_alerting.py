"""Acceptance tests AC-6..AC-11 for alert classification and the send rule."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from liquidity_forecaster.alerting import decide_send
from liquidity_forecaster.config import Config
from liquidity_forecaster.forecast import Severity, build_forecast
from liquidity_forecaster.models import AccountsResponse, PaymentsResponse
from liquidity_forecaster.store import Store

from . import fixtures


def _forecast(payments_payload: dict | None = None, include_drafts: bool = False):
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payload = payments_payload or fixtures.payments_response()
    payments = PaymentsResponse.model_validate(payload).payments
    return build_forecast(
        accounts, payments, Config(), today=fixtures.TODAY, include_drafts=include_drafts
    )


def test_ac6_red_breach_shortfall_and_drivers() -> None:
    f = _forecast()
    assert f.severity is Severity.RED
    assert f.first_breach_date == date(2026, 6, 25)
    assert f.shortfall == Decimal("160000.00")
    drivers = {i.creditor for i in f.drivers}
    assert drivers == {"Sound & Light AS", "Payroll"}


def test_ac7_draw_on_savings_clears() -> None:
    f = _forecast()
    assert f.draw_on_savings_clears is True  # 90 000 + 300 000 >= 250 000


def test_ac8_retrying_forces_red() -> None:
    payload = fixtures.payments_response()
    # A small payment that wouldn't breach the floor on its own, but is retrying.
    payload["payments"] = [
        {
            "id": "r1",
            "eventId": "r1",
            "createdAt": "2026-06-01T08:00:00Z",
            "createdByAgentId": "00000000-0000-0000-0000-000000000000",
            "state": "RetryingInsufficientFunds",
            "creditor": {"name": "Supplier", "accountNumber": "9999999999"},
            "debtorAccountNumber": fixtures.OPERATIONAL_ACCOUNT,
            "currencyAmount": {"amount": "1000.00", "currency": "NOK"},
            "executionDate": "2026-06-12",
        }
    ]
    f = _forecast(payload)
    assert f.has_retrying is True
    assert f.severity is Severity.RED


def test_ac9_state_change_only(tmp_path) -> None:
    store = Store(str(tmp_path / "s.db"))
    config = Config()
    f = _forecast()
    # First evaluation: should send.
    first = decide_send(f, store.last_alert(), config)
    assert first.should_send is True
    store.record_alert(f, created_at="2026-06-10", delivered_via="dry-run")
    # Identical re-run next day: nothing changed → silent.
    second = decide_send(f, store.last_alert(), config)
    assert second.should_send is False
    store.close()


def test_ac11_low_confidence_flagged() -> None:
    payload = fixtures.accounts_response()
    stale = "2026-06-01T08:00:00Z"
    payload["accounts"][0]["matchingTransactionsAt"] = stale
    accounts = AccountsResponse.model_validate(payload).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    f = build_forecast(accounts, payments, Config(), today=fixtures.TODAY)
    assert f.low_confidence is True


def test_green_first_run_is_silent(tmp_path) -> None:
    # No operational payments → stays at 480 000, above amber (312 500).
    payload = {"payments": []}
    f = _forecast(payload)
    assert f.severity is Severity.GREEN
    decision = decide_send(f, None, Config())
    assert decision.should_send is False


def test_recovery_sends_all_clear() -> None:
    from liquidity_forecaster.store import AlertRecord

    config = Config()
    green = _forecast({"payments": []})
    last = AlertRecord(
        level=Severity.RED,
        trough_date=date(2026, 6, 25),
        trough_balance=Decimal("90000.00"),
        breach_first_date=date(2026, 6, 25),
        delivered_via="slack",
    )
    decision = decide_send(green, last, config)
    assert decision.should_send is True
    assert "recovered" in decision.reason


def test_payments_outside_horizon_ignored() -> None:
    payload = fixtures.payments_response()
    far = fixtures.TODAY + timedelta(days=400)
    payload["payments"].append(
        {
            "id": "far",
            "eventId": "far",
            "createdAt": "2026-06-01T08:00:00Z",
            "createdByAgentId": "00000000-0000-0000-0000-000000000000",
            "state": "InProcess",
            "creditor": {"name": "FarFuture", "accountNumber": "9999999999"},
            "debtorAccountNumber": fixtures.OPERATIONAL_ACCOUNT,
            "currencyAmount": {"amount": "999999.00", "currency": "NOK"},
            "executionDate": far.isoformat(),
        }
    )
    f = _forecast(payload)
    assert "FarFuture" not in {i.creditor for i in f.items}
