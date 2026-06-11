"""Projection engine.

v1 is deterministic and conservative (docs/03-forecast.md): the projected
operational balance is the current balance plus the signed deltas of scheduled
payments, placed on their execution date. No recurring run-rate baseline in v1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import IntEnum

from .config import Config
from .models import Account, AccountType, Payment, PaymentState

log = logging.getLogger(__name__)

# Scenario → which payment states count as outflows on the curve.
_COMMITTED = {PaymentState.IN_PROCESS, PaymentState.RETRYING_INSUFFICIENT_FUNDS}
_DRAFTS = _COMMITTED | {PaymentState.DRAFT}

_BASE_CURRENCY = "NOK"


class Severity(IntEnum):
    GREEN = 0
    AMBER = 1
    RED = 2


@dataclass(frozen=True)
class ScheduledItem:
    """A scheduled payment as a signed delta on the operational balance.

    ``delta`` is negative for an outflow. A negative payment amount (e.g. a
    refund) therefore yields a positive delta.
    """

    execution_date: date
    creditor: str
    amount: Decimal  # the raw payment amount (outflow magnitude)
    delta: Decimal  # signed effect on balance
    state: PaymentState
    currency: str = _BASE_CURRENCY


@dataclass(frozen=True)
class Forecast:
    operational_account: str
    start_date: date
    end_date: date
    start_balance: Decimal
    savings_balance: Decimal
    floor: Decimal
    amber_threshold: Decimal
    curve: list[tuple[date, Decimal]]
    items: list[ScheduledItem]
    trough_date: date
    trough_balance: Decimal
    first_breach_date: date | None
    severity: Severity
    has_retrying: bool
    low_confidence: bool
    fx_variable: bool = False

    @property
    def shortfall(self) -> Decimal:
        """How far the trough sits below the floor (0 if above)."""
        gap = self.floor - self.trough_balance
        return gap if gap > 0 else Decimal(0)

    @property
    def drivers(self) -> list[ScheduledItem]:
        """Outflows that drive the dip: those up to and including the trough."""
        return [i for i in self.items if i.delta < 0 and i.execution_date <= self.trough_date]

    @property
    def draw_on_savings_clears(self) -> bool:
        return self.trough_balance + self.savings_balance >= self.floor


def scheduled_items(
    payments: list[Payment],
    operational_account: str,
    *,
    start: date,
    end: date,
    include_drafts: bool,
) -> list[ScheduledItem]:
    """Filter payments to operational-account scheduled items within the window."""
    states = _DRAFTS if include_drafts else _COMMITTED
    items: list[ScheduledItem] = []
    for p in payments:
        if p.debtor_account_number != operational_account:
            continue
        if p.state not in states:
            continue
        if not (start <= p.execution_date <= end):
            continue
        amount = p.currency_amount.amount
        items.append(
            ScheduledItem(
                execution_date=p.execution_date,
                creditor=p.creditor.name,
                amount=amount,
                delta=-amount,
                state=p.state,
                currency=p.currency_amount.currency,
            )
        )
    items.sort(key=lambda i: i.execution_date)
    return items


def build_forecast(
    accounts: list[Account],
    payments: list[Payment],
    config: Config,
    *,
    today: date,
    include_drafts: bool = False,
) -> Forecast:
    """Project the operational balance over the horizon and classify severity."""
    operational = _select_operational(accounts, config.operational_account)
    savings = _optional(accounts, AccountType.SAVINGS)
    savings_balance = savings.balance if savings else Decimal(0)

    start = today
    end = today + timedelta(days=config.horizon_days)
    items = scheduled_items(
        payments, operational.account_number, start=start, end=end, include_drafts=include_drafts
    )

    # Aggregate deltas by date, then walk the horizon day by day.
    by_date: dict[date, Decimal] = {}
    for item in items:
        by_date[item.execution_date] = by_date.get(item.execution_date, Decimal(0)) + item.delta

    curve: list[tuple[date, Decimal]] = []
    balance = operational.balance
    day = start
    while day <= end:
        balance += by_date.get(day, Decimal(0))
        curve.append((day, balance))
        day += timedelta(days=1)

    trough_date, trough_balance = min(curve, key=lambda dp: (dp[1], dp[0]))
    first_breach = next((d for d, b in curve if b < config.operational_floor), None)
    has_retrying = any(i.state is PaymentState.RETRYING_INSUFFICIENT_FUNDS for i in items)

    amber = config.amber_threshold()
    if trough_balance < config.operational_floor or has_retrying:
        severity = Severity.RED
    elif trough_balance < amber:
        severity = Severity.AMBER
    else:
        severity = Severity.GREEN

    low_confidence = operational.matching_transactions_at.date() < (today - timedelta(days=2))

    fx_items = [i for i in items if i.currency != _BASE_CURRENCY]
    if fx_items:
        log.warning(
            "%d scheduled payment(s) are not in %s; counted at face value — "
            "the NOK debit is not fixed until execution (FX-variable)",
            len(fx_items),
            _BASE_CURRENCY,
        )

    return Forecast(
        operational_account=operational.account_number,
        start_date=start,
        end_date=end,
        start_balance=operational.balance,
        savings_balance=savings_balance,
        floor=config.operational_floor,
        amber_threshold=amber,
        curve=curve,
        items=items,
        trough_date=trough_date,
        trough_balance=trough_balance,
        first_breach_date=first_breach,
        severity=severity,
        has_retrying=has_retrying,
        low_confidence=low_confidence,
        fx_variable=bool(fx_items),
    )


def _select_operational(accounts: list[Account], configured: str | None) -> Account:
    """Pick the Operational account to forecast.

    If ``configured`` is set, require that exact account. Otherwise take the single
    Operational account, or — when several exist — warn and pick deterministically
    (lowest account number) so the choice is stable across runs.
    """
    operational = [a for a in accounts if a.type is AccountType.OPERATIONAL]
    if not operational:
        raise ValueError("no Operational account found")
    if configured is not None:
        match = next((a for a in operational if a.account_number == configured), None)
        if match is None:
            raise ValueError(f"configured Operational account {configured} not found")
        return match
    if len(operational) > 1:
        chosen = min(operational, key=lambda a: a.account_number)
        log.warning(
            "%d Operational accounts found; forecasting %s. Set FOLIO_OPERATIONAL_ACCOUNT "
            "to choose explicitly.",
            len(operational),
            chosen.account_number,
        )
        return chosen
    return operational[0]


def _optional(accounts: list[Account], account_type: AccountType) -> Account | None:
    return next((a for a in accounts if a.type is account_type), None)
