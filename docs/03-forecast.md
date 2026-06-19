# 03 · Forecast methodology

**Part of the [Liquidity Forecaster spec](../README.md).**

---

## 1. Model (v1 — deterministic baseline)

For each account, projected balance on day *d*:

```
balance(d) = balance(today)
           + Σ scheduled_inflows(today..d)      // from /payments, /events
           − Σ scheduled_outflows(today..d)     // committed payments by executionDate
           + recurring_baseline(today..d)       // est. from historical trend (phase 2)
```

- **Day 0** = current `balance` from `GET /accounts`.
- **Scheduled items** are placed on their `executionDate`.
- **Recurring baseline** (phase 2): a per-weekday/per-month average daily net flow
  derived from [historical balance](02-data-and-accounts.md#22-historical-balance-trend--get-accountsaccountnumberbalancedate).
  v1 can run with baseline = 0 and rely purely on scheduled items + current balance
  for a conservative projection. See §4 for how the baseline avoids double-counting.

## 2. Horizon & granularity
- Default horizon: **8 weeks (56 days)**, configurable.
- Granularity: **daily**. Alerting evaluates the daily minimum.

## 3. Scenarios
- **Committed** (default): only `InProcess` + `RetryingInsufficientFunds` outflows.
- **Committed + Drafts**: adds `Draft` payments (pessimistic on outflow).
- **With reserves**: operational + savings line, to show buffered runway.

### Output of a forecast run
- Per-day projected balance for Operational (and Operational+Savings).
- The list of scheduled items driving each day's change.
- Identified **risk dates**: days where projected balance < floor.
- Headroom: `min(projected balance over horizon) − floor`.

---

## 4. Recurring baseline & double-count avoidance

> **Implemented** in `baseline.py` (`compute_baseline`) and applied in `forecast.py`.
> Enabled by default (`FORECAST_BASELINE=on`); needs daily-balance history, which the
> scheduled workflow refreshes via `sync-history` before each run. Expected client
> inflows (`inflows.py`, `EXPECTED_INFLOWS_FILE`) and FX conversion of foreign payments
> (`FX_RATES`) are also implemented and layered into the projection.

The baseline must capture *routine* run-rate (rent, payroll, subscriptions, steady card
spend) but **must not** re-add the large, irregular festival/wedding flows that the
projection already counts as scheduled items. The rule:

1. **Build the historical daily net series.** For each past day in the lookback window
   (default 90 days), `net(day) = outgoingBalance − incomingBalance` on the operational
   account.
2. **Strip the lumpy days.** Robustly flag outlier days using a median-based threshold:
   compute the median and MAD (median absolute deviation) of `net(day)`; mark any day
   where `|net(day) − median| > k · MAD` (default **k = 3.5**) as *lumpy* and exclude
   it from the baseline. MAD is used instead of mean/stdev so the very outliers we want
   to drop don't inflate the threshold.
3. **Cross-check against known large items.** Additionally exclude days whose net is
   dominated by a transaction matchable to a one-off scheduled payment (by amount/date
   via `/accounts/{n}/transactions`), so a festival payout is never both in the baseline
   *and* in the scheduled stream.
4. **Estimate the run-rate** from the remaining "ordinary" days only — e.g. an average
   net **per weekday** (Mon–Sun) to preserve weekly structure (payroll/rent cadence),
   plus an optional month-phase adjustment.
5. **Apply forward**, but only on days that have **no scheduled item** of their own; on
   a day that already carries a scheduled payment, the scheduled amount wins and the
   baseline is suppressed for that item's category to avoid overlap.
6. **Label baseline contribution separately** in the output so a dip caused by run-rate
   vs. a dip caused by a specific scheduled payment are distinguishable.

> The `k` threshold, lookback window, and weekday-vs-monthly granularity are tunable
> config. Defaults chosen to be conservative (drop more as "lumpy" rather than risk
> smearing a festival payout across the baseline).

---

## 5. Worked example (v1, committed scenario, baseline = 0)

Illustrative numbers to make the model testable. Floor = 250 000, warning band = 25%
(amber ≤ 312 500). "Today" = 2026-06-10. This example doubles as the fixture for the
[acceptance tests](07-roadmap.md#2-acceptance-criteria).

**Starting balances** (`GET /accounts`):

| Account | Type | Balance (NOK) |
|---|---|---|
| Drift | Operational | 480 000.00 |
| Skatt | Tax | 220 000.00 |
| Øremerket | Earmarks | 150 000.00 |
| Sparing | Savings | 300 000.00 |

**Scheduled payments** debiting Operational
(`GET /payments?startDate=2026-06-10&endDate=2026-08-05`):

| executionDate | Creditor | Amount | state | Counted? |
|---|---|---|---|---|
| 2026-06-15 | Sound & Light AS | 180 000.00 | InProcess | ✅ outflow |
| 2026-06-25 | Payroll | 210 000.00 | InProcess | ✅ outflow |
| 2026-06-25 | Tax (employer) | 95 000.00 | Draft | ❌ (committed scenario) |
| 2026-07-10 | Venue deposit (refund in) | −120 000.00 | InProcess | ✅ inflow |
| 2026-05-30 | Catering | 60 000.00 | Completed | ❌ already in balance |

**Projected Operational balance (committed):**

| Date | Event | Balance after |
|---|---|---|
| 2026-06-10 | start | 480 000 |
| 2026-06-15 | − 180 000 (Sound & Light) | 300 000 |
| 2026-06-25 | − 210 000 (Payroll) | **90 000** ← trough |
| 2026-07-10 | + 120 000 (deposit refund) | 210 000 |
| … | (no further scheduled items) | 210 000 |

**Evaluation:**
- Trough = **90 000 NOK on 2026-06-25**, which is **< floor (250 000)** → **RED**.
- Shortfall vs floor at trough = 250 000 − 90 000 = **160 000 NOK**.
- First amber day = 2026-06-15 (balance 300 000 < amber 312 500, still above floor) —
  ~5 days out. The **floor breach (RED) date is 2026-06-25**, ~15 calendar days out;
  this is the `first_breach_date` the alert reports as the "first crossing".
- Drivers surfaced: Sound & Light (180 000), Payroll (210 000).
- "Draw on Savings clears it?" Savings = 300 000; 90 000 + 300 000 = 390 000 > floor →
  **yes, moving ≥ 160 000 from Savings restores the floor.** Alert says so.
- Slack `#finance` RED posts; if the post fails, the same alert emails kai@.

---

**Prev:** [← 02 · Data & accounts](02-data-and-accounts.md) · **Next:** [04 · Alerting →](04-alerting.md)
