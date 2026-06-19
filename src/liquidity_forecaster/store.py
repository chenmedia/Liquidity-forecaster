"""Local SQLite store: cached daily balances + alert state.

The file holds financial data, so it is created with ``0600`` permissions
(docs/06-security.md §5). Historical daily balances are immutable once settled,
so the sync is incremental — we only fetch dates we don't already have.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from .forecast import Forecast, Severity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_balance (
    account_number TEXT NOT NULL,
    day TEXT NOT NULL,
    incoming_balance TEXT,
    outgoing_balance TEXT,
    PRIMARY KEY (account_number, day)
);
CREATE TABLE IF NOT EXISTS alert_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    level INTEGER NOT NULL,
    trough_date TEXT NOT NULL,
    trough_balance TEXT NOT NULL,
    breach_first_date TEXT,
    delivered_via TEXT
);
"""


@dataclass(frozen=True)
class AlertRecord:
    level: Severity
    trough_date: date
    trough_balance: Decimal
    breach_first_date: date | None
    delivered_via: str | None


class Store:
    def __init__(self, path: str) -> None:
        self._path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        if path != ":memory:":
            os.chmod(path, 0o600)

    def close(self) -> None:
        self._conn.close()

    # --- daily balance history -----------------------------------------
    def has_balance(self, account_number: str, day: date) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM daily_balance WHERE account_number = ? AND day = ?",
            (account_number, day.isoformat()),
        )
        return cur.fetchone() is not None

    def put_balance(
        self, account_number: str, day: date, incoming: Decimal | None, outgoing: Decimal | None
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO daily_balance "
            "(account_number, day, incoming_balance, outgoing_balance) VALUES (?, ?, ?, ?)",
            (
                account_number,
                day.isoformat(),
                None if incoming is None else str(incoming),
                None if outgoing is None else str(outgoing),
            ),
        )
        self._conn.commit()

    def daily_nets(self, account_number: str, since: date) -> list[tuple[date, Decimal]]:
        """Per-day net flow (outgoing − incoming) since ``since``, for the baseline.

        Days where the account wasn't open (missing balances) are skipped.
        """
        cur = self._conn.execute(
            "SELECT day, incoming_balance, outgoing_balance FROM daily_balance "
            "WHERE account_number = ? AND day >= ? ORDER BY day",
            (account_number, since.isoformat()),
        )
        nets: list[tuple[date, Decimal]] = []
        for row in cur.fetchall():
            inc, out = row["incoming_balance"], row["outgoing_balance"]
            if inc is None or out is None:
                continue
            nets.append((date.fromisoformat(row["day"]), Decimal(out) - Decimal(inc)))
        return nets

    # --- alert state ----------------------------------------------------
    def last_alert(self) -> AlertRecord | None:
        cur = self._conn.execute("SELECT * FROM alert_state ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        return AlertRecord(
            level=Severity(row["level"]),
            trough_date=date.fromisoformat(row["trough_date"]),
            trough_balance=Decimal(row["trough_balance"]),
            breach_first_date=(
                date.fromisoformat(row["breach_first_date"]) if row["breach_first_date"] else None
            ),
            delivered_via=row["delivered_via"],
        )

    def record_alert(
        self, forecast: Forecast, *, created_at: str, delivered_via: str | None
    ) -> None:
        self._conn.execute(
            "INSERT INTO alert_state "
            "(created_at, level, trough_date, trough_balance, breach_first_date, delivered_via) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                created_at,
                int(forecast.severity),
                forecast.trough_date.isoformat(),
                str(forecast.trough_balance),
                forecast.first_breach_date.isoformat() if forecast.first_breach_date else None,
                delivered_via,
            ),
        )
        self._conn.commit()
