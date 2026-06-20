"""Tests for the dashboard data path: serialization and snapshot publishing."""

from __future__ import annotations

import json

from liquidity_forecaster import publish
from liquidity_forecaster.config import Config
from liquidity_forecaster.forecast import build_forecast
from liquidity_forecaster.models import AccountsResponse, PaymentsResponse
from liquidity_forecaster.serialize import forecast_to_dict

from . import fixtures


def _forecast():
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    return build_forecast(accounts, payments, Config(), today=fixtures.TODAY)


def test_forecast_to_dict_shape_and_values() -> None:
    d = forecast_to_dict(_forecast())
    assert d["severity"] == "RED"
    assert d["troughBalance"] == "90000.00"
    assert d["shortfall"] == "160000.00"
    assert d["firstBreachDate"] == "2026-06-25"
    assert {dr["creditor"] for dr in d["drivers"]} == {"Sound & Light AS", "Payroll"}
    assert len(d["curve"]) == Config().horizon_days + 1
    assert all(isinstance(p["balance"], str) for p in d["curve"])


def test_forecast_to_dict_is_json_serializable() -> None:
    json.dumps(forecast_to_dict(_forecast()))  # must not raise


def test_publish_skips_when_unconfigured(monkeypatch) -> None:
    for var in publish._URL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    assert publish.publish_snapshot({"a": 1}) is False


def test_publish_writes_via_connection(monkeypatch) -> None:
    """With a configured URL, it creates the table, inserts, prunes, and commits."""
    calls: list[str] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params=None):
            calls.append(sql.strip().split()[0].upper())  # first SQL keyword

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            calls.append("COMMIT")

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda url: FakeConn())
    ok = publish.publish_snapshot({"x": 1}, database_url="postgres://example/db")
    assert ok is True
    assert calls == ["CREATE", "INSERT", "DELETE", "COMMIT"]
