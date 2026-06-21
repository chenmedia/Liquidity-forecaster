"""Configuration.

Non-secret settings live here with safe defaults. **Secrets are never stored on
this object** — they are read from the environment at the moment of use
(see :mod:`liquidity_forecaster.folio_client` and :mod:`liquidity_forecaster.notify`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal


def _env_decimal(name: str, default: str) -> Decimal:
    # Treat an unset OR empty value as "use the default": GitHub Actions passes
    # `${{ vars.X }}` as an empty string when the variable is unset, and
    # os.environ.get(name, default) would return that empty string.
    return Decimal(os.environ.get(name) or default)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name) or str(default))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if not raw:  # unset or empty → default
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    # Empty (present-but-blank, as Actions passes unset vars) → default.
    return os.environ.get(name) or default


def _env_fx_rates(name: str) -> dict[str, Decimal]:
    """Parse a JSON map of currency→NOK rate, e.g. {"EUR": "11.50"}."""
    raw = os.environ.get(name)
    if not raw:
        return {}
    return {cur: Decimal(str(rate)) for cur, rate in json.loads(raw).items()}


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
        default_factory=lambda: _env_str("FOLIO_API_BASE_URL", "https://api.folio.no/v2")
    )
    # Disambiguates which Operational account to forecast when several exist.
    operational_account: str | None = field(
        default_factory=lambda: os.environ.get("FOLIO_OPERATIONAL_ACCOUNT") or None
    )

    # Notification routing (non-secret)
    slack_channel: str = field(default_factory=lambda: _env_str("SLACK_CHANNEL", "#finance"))
    alert_email_to: str = field(
        default_factory=lambda: _env_str("ALERT_EMAIL_TO", "kai@chenmedia.no")
    )

    # Local store
    db_path: str = field(default_factory=lambda: _env_str("FORECAST_DB_PATH", "data/forecaster.db"))

    # Phase 2
    enable_baseline: bool = field(default_factory=lambda: _env_bool("FORECAST_BASELINE", True))
    baseline_mad_k: Decimal = field(
        default_factory=lambda: _env_decimal("FORECAST_BASELINE_MAD_K", "3.5")
    )
    expected_inflows_file: str | None = field(
        default_factory=lambda: os.environ.get("EXPECTED_INFLOWS_FILE") or None
    )
    # Currency→NOK conversion rates for foreign payments, e.g. FX_RATES='{"EUR":"11.50"}'
    fx_rates: dict[str, Decimal] = field(default_factory=lambda: _env_fx_rates("FX_RATES"))

    def amber_threshold(self) -> Decimal:
        """Balance at/below which we go AMBER (but not yet RED)."""
        return self.operational_floor * (Decimal(100 + self.warning_band_pct) / Decimal(100))
