"""Backend helpers for the dashboard's internal compute function.

The Python function is **internal**: only the Next.js server (which performs the
Clerk user auth + email-domain allowlist) may call it, authenticated with a shared
``INTERNAL_API_SECRET``. It fails **closed** when the secret isn't configured.
"""

from __future__ import annotations

import hmac
import os

from .config import Config
from .pipeline import compute_forecast
from .serialize import forecast_to_dict
from .store import Store


class InternalAuthError(Exception):
    """Wrong or missing internal secret."""


class NotConfigured(Exception):
    """INTERNAL_API_SECRET is not set — refuse to serve data (fail closed)."""


def check_internal_secret(provided: str | None) -> None:
    """Validate the caller's internal secret with a constant-time comparison."""
    expected = os.environ.get("INTERNAL_API_SECRET")
    if not expected:
        raise NotConfigured("INTERNAL_API_SECRET is not set")
    if not provided or not hmac.compare_digest(provided, expected):
        raise InternalAuthError("invalid internal secret")


def build_payload() -> dict[str, object]:
    """Compute the current forecast and return it as a JSON-friendly dict."""
    config = Config()
    store = Store(config.db_path)
    try:
        forecast = compute_forecast(config, store)
        return forecast_to_dict(forecast)
    finally:
        store.close()
