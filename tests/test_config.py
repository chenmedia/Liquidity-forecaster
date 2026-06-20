"""Config env-var handling — empty values must fall back to defaults.

GitHub Actions renders `${{ vars.X }}` as an empty string when a variable is unset,
which would otherwise crash `_env_decimal`/`_env_int` (Decimal("")/int("")).
"""

from __future__ import annotations

from decimal import Decimal

from liquidity_forecaster.config import Config


def test_empty_env_vars_fall_back_to_defaults(monkeypatch) -> None:
    for var in ("FORECAST_FLOOR", "FORECAST_HORIZON_DAYS", "FORECAST_BASELINE"):
        monkeypatch.setenv(var, "")  # present but empty, as Actions passes them
    config = Config()
    assert config.operational_floor == Decimal("250000")
    assert config.horizon_days == 56
    assert config.enable_baseline is True


def test_set_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("FORECAST_FLOOR", "300000")
    monkeypatch.setenv("FORECAST_HORIZON_DAYS", "42")
    monkeypatch.setenv("FORECAST_BASELINE", "off")
    config = Config()
    assert config.operational_floor == Decimal("300000")
    assert config.horizon_days == 42
    assert config.enable_baseline is False
