"""Phase-2 tests: recurring baseline, expected inflows, FX conversion."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from liquidity_forecaster.baseline import compute_baseline
from liquidity_forecaster.config import Config
from liquidity_forecaster.forecast import Inflow, Severity, build_forecast, scheduled_items
from liquidity_forecaster.inflows import load_expected_inflows
from liquidity_forecaster.models import AccountsResponse, Payment, PaymentsResponse
from liquidity_forecaster.notify.message import render_text

from . import fixtures


def _accounts():
    return AccountsResponse.model_validate(fixtures.accounts_response()).accounts


# ── Recurring baseline ────────────────────────────────────────────────────────


def test_compute_baseline_excludes_lumpy_days() -> None:
    # 8 weeks of routine −1 000/day, plus two huge festival days that must be dropped.
    nets: list[tuple[date, Decimal]] = []
    start = date(2026, 3, 1)
    for i in range(56):
        nets.append((start + timedelta(days=i), Decimal("-1000")))
    nets.append((start + timedelta(days=60), Decimal("-250000")))  # lumpy payout
    nets.append((start + timedelta(days=61), Decimal("400000")))  # lumpy inflow
    baseline = compute_baseline(nets, k=Decimal("3.5"))
    assert baseline  # non-empty
    # Every weekday average should be the routine −1 000, not skewed by the outliers.
    assert all(v == Decimal("-1000.00") for v in baseline.values())


def test_compute_baseline_returns_empty_when_thin() -> None:
    nets = [(date(2026, 3, 1), Decimal("-1000"))]
    assert compute_baseline(nets) == {}


def test_baseline_applied_lowers_projection() -> None:
    # No scheduled payments → balance drifts down by the baseline each day.
    payments: list[Payment] = []
    baseline = dict.fromkeys(range(7), Decimal("-1000"))
    f = build_forecast(_accounts(), payments, Config(), today=fixtures.TODAY, baseline=baseline)
    assert f.baseline_applied is True
    # 56 horizon days after start, each −1 000 → 480 000 − 56 000.
    assert f.curve[-1][1] == Decimal("424000")
    assert "run-rate baseline" in render_text(f)


# ── Expected inflows ──────────────────────────────────────────────────────────


def test_expected_inflow_raises_balance_and_shows_in_message() -> None:
    inflow = Inflow(
        date=fixtures.TODAY + timedelta(days=5), amount=Decimal("100000"), source="Festival X"
    )
    payments = PaymentsResponse.model_validate({"payments": []}).payments
    f = build_forecast(
        _accounts(), payments, Config(), today=fixtures.TODAY, expected_inflows=[inflow]
    )
    assert f.inflows == [inflow]
    by_date = dict(f.curve)
    assert by_date[fixtures.TODAY + timedelta(days=5)] == Decimal("580000")
    assert "Festival X" in render_text(f)


def test_load_expected_inflows(tmp_path) -> None:
    p = tmp_path / "inflows.json"
    p.write_text(
        json.dumps(
            [
                {"date": "2026-07-05", "amount": "120000.00", "source": "Festival balance"},
                {"date": "2026-07-20", "amount": "45000.00", "source": "Wedding — Hansen"},
            ]
        )
    )
    inflows = load_expected_inflows(str(p))
    assert [i.amount for i in inflows] == [Decimal("120000.00"), Decimal("45000.00")]


def test_load_expected_inflows_missing_returns_empty() -> None:
    assert load_expected_inflows(None) == []
    assert load_expected_inflows("/no/such/file.json") == []


def test_load_expected_inflows_rejects_bad_entry(tmp_path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"date": "2026-07-05", "amount": "-5"}]))
    with pytest.raises(ValueError):
        load_expected_inflows(str(p))


# ── FX conversion ─────────────────────────────────────────────────────────────


def _eur_payment(amount: str = "5000.00", currency: str = "EUR") -> dict:
    return {
        "payments": [
            {
                "id": "fx1",
                "eventId": "fx1",
                "createdAt": "2026-06-01T08:00:00Z",
                "createdByAgentId": "00000000-0000-0000-0000-000000000000",
                "state": "InProcess",
                "creditor": {"name": "EU Vendor", "accountNumber": "9999999999"},
                "debtorAccountNumber": fixtures.OPERATIONAL_ACCOUNT,
                "currencyAmount": {"amount": amount, "currency": currency},
                "executionDate": "2026-06-20",
            }
        ]
    }


def test_fx_converted_when_rate_present() -> None:
    payments = PaymentsResponse.model_validate(_eur_payment()).payments
    items = scheduled_items(
        payments,
        fixtures.OPERATIONAL_ACCOUNT,
        start=fixtures.TODAY,
        end=fixtures.TODAY + timedelta(days=56),
        include_drafts=False,
        fx_rates={"EUR": Decimal("11.50")},
    )
    assert len(items) == 1
    assert items[0].converted is True
    assert items[0].currency == "EUR"
    assert items[0].amount == Decimal("57500.00")  # 5000 × 11.50


def test_fx_face_value_when_no_rate() -> None:
    payments = PaymentsResponse.model_validate(_eur_payment(currency="USD")).payments
    f = build_forecast(
        _accounts(), payments, Config(fx_rates={"EUR": Decimal("11.5")}), today=fixtures.TODAY
    )
    fx_item = next(i for i in f.items if i.currency == "USD")
    assert fx_item.converted is False
    assert fx_item.amount == Decimal("5000.00")  # face value
    assert f.fx_variable is True  # still flagged — rate not locked


def test_severity_unchanged_for_small_fx() -> None:
    # A small converted FX outflow shouldn't breach the floor on its own.
    payments = PaymentsResponse.model_validate(_eur_payment()).payments
    f = build_forecast(
        _accounts(), payments, Config(fx_rates={"EUR": Decimal("11.5")}), today=fixtures.TODAY
    )
    assert f.severity is Severity.GREEN
