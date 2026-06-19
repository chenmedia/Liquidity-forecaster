"""Load expected client inflows (phase 2).

Lets the owner record festival/wedding invoices they expect to be paid but which
aren't yet scheduled in Folio, so the projection isn't outflow-only. The file is
a JSON list:

    [
      {"date": "2026-07-05", "amount": "120000.00", "source": "Festival X balance"},
      {"date": "2026-07-20", "amount": "45000.00",  "source": "Wedding — Hansen"}
    ]

Amounts are NOK decimal strings (positive). Path comes from EXPECTED_INFLOWS_FILE.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .forecast import Inflow

log = logging.getLogger(__name__)


def load_expected_inflows(path: str | None) -> list[Inflow]:
    """Parse the expected-inflows file, or return [] if unset/missing."""
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        log.warning("EXPECTED_INFLOWS_FILE %s not found; skipping expected inflows", path)
        return []

    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"expected-inflows file {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError(f"expected-inflows file {path} must contain a JSON list")

    inflows: list[Inflow] = []
    for entry in raw:
        try:
            amount = Decimal(str(entry["amount"]))
            if amount <= 0:
                raise ValueError("amount must be positive")
            inflows.append(
                Inflow(
                    date=date.fromisoformat(entry["date"]),
                    amount=amount,
                    source=str(entry.get("source", "expected inflow")),
                )
            )
        except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
            raise ValueError(f"invalid expected-inflow entry {entry!r}: {exc}") from exc
    return inflows
