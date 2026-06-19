"""Tests for the dashboard backend: serialization and the auth gate."""

from __future__ import annotations

import json

import pytest

from liquidity_forecaster import web
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
    # Money stays as strings (never float).
    assert all(isinstance(p["balance"], str) for p in d["curve"])


def test_forecast_to_dict_is_json_serializable() -> None:
    json.dumps(forecast_to_dict(_forecast()))  # must not raise


def test_check_token_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    with pytest.raises(web.NotConfigured):
        web.check_token("anything")


def test_check_token_rejects_wrong(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    with pytest.raises(web.Unauthorized):
        web.check_token("nope")
    with pytest.raises(web.Unauthorized):
        web.check_token(None)


def test_check_token_accepts_correct(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    web.check_token("s3cret")  # must not raise
