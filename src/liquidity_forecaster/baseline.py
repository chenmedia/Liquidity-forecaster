"""Recurring run-rate baseline (phase 2, docs/03-forecast.md §4).

Estimates a routine per-weekday net cash flow from the operational account's
historical daily balances, *excluding* lumpy festival/wedding days so the big
irregular flows aren't smeared into the baseline. Lumpy days are detected with a
median/MAD threshold (robust to the very outliers we want to drop).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from statistics import median


def _mad(values: list[Decimal], med: Decimal) -> Decimal:
    """Median absolute deviation."""
    if not values:
        return Decimal(0)
    return median([abs(v - med) for v in values])


def compute_baseline(
    daily_nets: list[tuple[date, Decimal]],
    *,
    k: Decimal = Decimal("3.5"),
    min_ordinary_days: int = 14,
) -> dict[int, Decimal]:
    """Return a per-weekday (0=Mon … 6=Sun) average net flow, lumpy days removed.

    ``daily_nets`` is ``(day, net)`` where ``net = outgoing − incoming`` for that
    day. Returns an empty mapping when there is too little ordinary history to be
    meaningful (caller then runs with no baseline).
    """
    if len(daily_nets) < min_ordinary_days:
        return {}

    nets = [n for _, n in daily_nets]
    med = median(nets)
    mad = _mad(nets, med)

    # Keep "ordinary" days: within k·MAD of the median. When MAD is zero (a very
    # flat routine), any deviation from the median is an outlier, so keep only the
    # days that equal the median.
    if mad == 0:
        ordinary = [(d, n) for d, n in daily_nets if n == med]
    else:
        threshold = k * mad
        ordinary = [(d, n) for d, n in daily_nets if abs(n - med) <= threshold]
    if len(ordinary) < min_ordinary_days:
        return {}

    by_weekday: dict[int, list[Decimal]] = defaultdict(list)
    for d, n in ordinary:
        by_weekday[d.weekday()].append(n)

    return {
        wd: (sum(vals) / Decimal(len(vals))).quantize(Decimal("0.01"))
        for wd, vals in by_weekday.items()
    }
