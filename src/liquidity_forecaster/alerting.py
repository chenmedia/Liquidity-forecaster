"""Alert decision: should this forecast be sent, given the last alert?

Implements the state-change-only send rule (docs/04-alerting.md §4.4) so an
unchanged amber is not re-sent every day.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .config import Config
from .forecast import Forecast, Severity
from .store import AlertRecord


@dataclass(frozen=True)
class SendDecision:
    should_send: bool
    reason: str


def decide_send(forecast: Forecast, last: AlertRecord | None, config: Config) -> SendDecision:
    """Decide whether to notify, comparing against the last recorded alert."""
    # Already short on funds → always surface.
    if forecast.has_retrying:
        return SendDecision(True, "payment retrying for insufficient funds")

    if last is None:
        # First evaluation: notify unless everything is comfortably green.
        if forecast.severity is Severity.GREEN:
            return SendDecision(False, "first run, green")
        return SendDecision(True, "first alert")

    if forecast.severity > last.level:
        return SendDecision(True, f"severity worsened {last.level.name}→{forecast.severity.name}")

    if forecast.severity < last.level:
        return SendDecision(True, f"recovered to {forecast.severity.name}")

    # Same severity: only re-send on a material worsening of the trough.
    if forecast.severity is not Severity.GREEN:
        if (
            forecast.first_breach_date
            and last.breach_first_date
            and forecast.first_breach_date < last.breach_first_date
        ):
            return SendDecision(True, "breach date moved earlier")
        if _material_drop(
            last.trough_balance, forecast.trough_balance, config.trough_change_delta_pct
        ):
            return SendDecision(True, "trough worsened materially")

    return SendDecision(False, f"unchanged {forecast.severity.name}")


def _material_drop(previous: Decimal, current: Decimal, delta_pct: int) -> bool:
    """True if ``current`` is materially lower than ``previous``."""
    if current >= previous:
        return False
    threshold = abs(previous) * Decimal(delta_pct) / Decimal(100)
    if threshold == 0:
        return current < previous
    return (previous - current) >= threshold
