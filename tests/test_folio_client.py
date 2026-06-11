"""Client tests: read-only surface, auth header, validation, future-cutoff guard."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from liquidity_forecaster.config import Config
from liquidity_forecaster.folio_client import FolioAuthError, FolioClient

from . import fixtures

BASE = "https://api.folio.no/v2"


@pytest.fixture
def api_key(monkeypatch) -> None:
    monkeypatch.setenv("FOLIO_API_KEY", "fk.test-key-not-real-000000")


def test_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("FOLIO_API_KEY", raising=False)
    with pytest.raises(FolioAuthError):
        FolioClient(Config())


@respx.mock
def test_get_accounts_sends_bearer_and_validates(api_key) -> None:
    route = respx.get(f"{BASE}/accounts").mock(
        return_value=httpx.Response(200, json=fixtures.accounts_response())
    )
    with FolioClient(Config()) as client:
        resp = client.get_accounts()
    assert route.called
    assert route.calls.last.request.headers["Authorization"].startswith("Bearer ")
    assert len(resp.accounts) == 4


@respx.mock
def test_get_payments_always_sends_explicit_end_date(api_key) -> None:
    route = respx.get(f"{BASE}/payments").mock(
        return_value=httpx.Response(200, json=fixtures.payments_response())
    )
    with FolioClient(Config()) as client:
        client.get_payments(date(2026, 6, 10), date(2026, 8, 5))
    params = route.calls.last.request.url.params
    assert params["startDate"] == "2026-06-10"
    assert params["endDate"] == "2026-08-05"  # AC-4: never defaults to today


def test_client_has_no_mutating_methods() -> None:
    # AC-13: read-only by construction — the public surface is exactly the read calls.
    public = {n for n in dir(FolioClient) if not n.startswith("_")}
    assert public == {"close", "get_accounts", "get_balance", "get_payments"}


def test_get_payments_rejects_inverted_range(api_key) -> None:
    with FolioClient(Config()) as client, pytest.raises(ValueError):
        client.get_payments(date(2026, 8, 5), date(2026, 6, 10))
