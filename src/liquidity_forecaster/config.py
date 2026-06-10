"""Configuration.

Non-secret settings live here with safe defaults. **Secrets are never stored on
this object** — they are read from the environment at the moment of use
(see :mod:`liquidity_forecaster.folio_client` and :mod:`liquidity_forecaster.notify`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Config:
    """Runtime configuration (non-secret).

    Defaults match the spec (docs/04-alerting.md §4.1). They are starting points
    to confirm against real numbers — the ``accounts`` command prints balances so
    the floor can be right-sized before alerts are enabled.
    """

    # Alerting thresholds
    operational_floor: Decimal = field(
        default_factory=lambda: _env_decimal("FORECAST_FLOOR", "250000")
    )
    warning_band_pct: int = field(default_factory=lambda: _env_int("FORECAST_WARNING_BAND_PCT", 25))
    horizon_days: int = field(default_factory=lambda: _env_int("FORECAST_HORIZON_DAYS", 56))
    lookback_days: int = field(default_factory=lambda: _env_int("FORECAST_LOOKBACK_DAYS", 90))
    trough_change_delta_pct: int = field(
        default_factory=lambda: _env_int("FORECAST_TROUGH_DELTA_PCT", 5)
    )

    # Folio API
    folio_base_url: str = field(
        default_factory=lambda: os.environ.get("FOLIO_API_BASE_URL", "https://api.folio.no/v2")
    )

    # Notification routing (non-secret)
    slack_channel: str = field(default_factory=lambda: os.environ.get("SLACK_CHANNEL", "#finance"))
    alert_email_to: str = field(
        default_factory=lambda: os.environ.get("ALERT_EMAIL_TO", "kai@chenmedia.no")
    )

    # Local store
    db_path: str = field(
        default_factory=lambda: os.environ.get("FORECAST_DB_PATH", "data/forecaster.db")
    )

    def amber_threshold(self) -> Decimal:
        """Balance at/below which we go AMBER (but not yet RED)."""
        return self.operational_floor * (Decimal(100 + self.warning_band_pct) / Decimal(100))
