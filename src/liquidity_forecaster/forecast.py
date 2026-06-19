"""Projection engine.

The projected operational balance is the current balance plus, day by day:
  - signed deltas of scheduled payments (placed on their execution date),
  - expected client inflows (phase 2),
  - a recurring run-rate baseline on days with no scheduled item (phase 2).

Foreign-currency payments are converted to NOK using configured FX rates when
available (otherwise counted at face value); either way they are flagged
FX-variable because the rate is not fixed until execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    refund) therefore yields a positive delta. For foreign payments ``amount``
    and ``delta`` are in NOK after conversion; ``currency`` keeps the original.
    """

    execution_date: date
    creditor: str
    amount: Decimal  # NOK magnitude (converted if foreign)
    delta: Decimal  # signed NOK effect on balance
    state: PaymentState
    currency: str = _BASE_CURRENCY
    converted: bool = False


@dataclass(frozen=True)
class Inflow:
    """An expected client payment not yet represented in Folio (phase 2)."""

    date: date
    amount: Decimal  # NOK, positive
    source: str


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
    inflows: list[Inflow] = field(default_factory=list)
    baseline_applied: bool = False

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
    fx_rates: dict[str, Decimal] | None = None,
) -> list[ScheduledItem]:
    """Filter payments to operational-account scheduled items within the window."""
    rates = fx_rates or {}
    states = _DRAFTS if include_drafts else _COMMITTED
    items: list[ScheduledItem] = []
    for p in payments:
        if p.debtor_account_number != operational_account:
            continue
        if p.state not in states:
            continue
        if not (start <= p.execution_date <= end):
            continue
        currency = p.currency_amount.currency
        amount = p.currency_amount.amount
        converted = False
        if currency != _BASE_CURRENCY and currency in rates:
            amount = (amount * rates[currency]).quantize(Decimal("0.01"))
            converted = True
        items.append(
            ScheduledItem(
                execution_date=p.execution_date,
                creditor=p.creditor.name,
                amount=amount,
                delta=-amount,
                state=p.state,
                currency=currency,
                converted=converted,
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
    baseline: dict[int, Decimal] | None = None,
    expected_inflows: list[Inflow] | None = None,
) -> Forecast:
    """Project the operational balance over the horizon and classify severity."""
    operational = _select_operational(accounts, config.operational_account)
    savings = _optional(accounts, AccountType.SAVINGS)
    savings_balance = savings.balance if savings else Decimal(0)

    start = today
    end = today + timedelta(days=config.horizon_days)
    items = scheduled_items(
        payments,
        operational.account_number,
        start=start,
        end=end,
        include_drafts=include_drafts,
        fx_rates=config.fx_rates,
    )
    inflows = [i for i in (expected_inflows or []) if start <= i.date <= end]

    # Aggregate scheduled deltas by date (payments + expected inflows).
    by_date: dict[date, Decimal] = {}
    for item in items:
        by_date[item.execution_date] = by_date.get(item.execution_date, Decimal(0)) + item.delta
    for inflow in inflows:
        by_date[inflow.date] = by_date.get(inflow.date, Decimal(0)) + inflow.amount

    # Walk the horizon; on days with no scheduled item, apply the run-rate baseline.
    curve: list[tuple[date, Decimal]] = []
    balance = operational.balance
    day = start
    while day <= end:
        if day in by_date:
            balance += by_date[day]
        elif baseline and day > start:
            balance += baseline.get(day.weekday(), Decimal(0))
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
        unconverted = [i for i in fx_items if not i.converted]
        log.warning(
            "%d non-NOK payment(s): %d converted via FX rates, %d at face value — "
            "NOK debit not fixed until execution (FX-variable)",
            len(fx_items),
            len(fx_items) - len(unconverted),
            len(unconverted),
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
        inflows=inflows,
        baseline_applied=bool(baseline),
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
