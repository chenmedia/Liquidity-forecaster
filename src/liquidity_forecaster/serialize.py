"""Serialize a :class:`Forecast` to a JSON-friendly dict for the web dashboard.

Money stays as decimal strings (never float) so the frontend formats it itself.
"""

from __future__ import annotations

from .forecast import Forecast


def forecast_to_dict(f: Forecast) -> dict[str, object]:
    return {
        "severity": f.severity.name,
        "operationalAccount": f.operational_account,
        "startDate": f.start_date.isoformat(),
        "endDate": f.end_date.isoformat(),
        "startBalance": str(f.start_balance),
        "floor": str(f.floor),
        "amberThreshold": str(f.amber_threshold),
        "troughDate": f.trough_date.isoformat(),
        "troughBalance": str(f.trough_balance),
        "shortfall": str(f.shortfall),
        "firstBreachDate": f.first_breach_date.isoformat() if f.first_breach_date else None,
        "savingsBalance": str(f.savings_balance),
        "drawOnSavingsClears": f.draw_on_savings_clears,
        "flags": {
            "hasRetrying": f.has_retrying,
            "lowConfidence": f.low_confidence,
            "fxVariable": f.fx_variable,
            "baselineApplied": f.baseline_applied,
        },
        "curve": [{"date": d.isoformat(), "balance": str(b)} for d, b in f.curve],
        "drivers": [
            {
                "date": i.execution_date.isoformat(),
                "creditor": i.creditor,
                "amount": str(i.amount),
                "currency": i.currency,
            }
            for i in f.drivers
        ],
        "inflows": [
            {"date": i.date.isoformat(), "source": i.source, "amount": str(i.amount)}
            for i in f.inflows
        ],
    }
