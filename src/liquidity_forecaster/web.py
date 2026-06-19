"""Backend helpers for the web dashboard.

The dashboard exposes live financial data, so the API is gated by a shared secret
(``DASHBOARD_TOKEN``) and fails **closed** when it isn't configured. This module
keeps the auth + payload logic here (testable) so the serverless handler stays thin.
"""

from __future__ import annotations

import hmac
import os

from .config import Config
from .pipeline import compute_forecast
from .serialize import forecast_to_dict
from .store import Store


class Unauthorized(Exception):
    """Wrong or missing dashboard token."""


class NotConfigured(Exception):
    """DASHBOARD_TOKEN is not set — refuse to serve data (fail closed)."""


def check_token(provided: str | None) -> None:
    """Validate the caller's token with a constant-time comparison."""
    expected = os.environ.get("DASHBOARD_TOKEN")
    if not expected:
        raise NotConfigured("DASHBOARD_TOKEN is not set")
    if not provided or not hmac.compare_digest(provided, expected):
        raise Unauthorized("invalid dashboard token")


def build_payload() -> dict[str, object]:
    """Compute the current forecast and return it as a JSON-friendly dict."""
    config = Config()
    store = Store(config.db_path)
    try:
        forecast = compute_forecast(config, store)
        return forecast_to_dict(forecast)
    finally:
        store.close()
