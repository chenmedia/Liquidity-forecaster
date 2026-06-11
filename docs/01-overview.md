# 01 · Overview

**Part of the [Liquidity Forecaster spec](../README.md).**
**Data source:** Folio API v2 (`https://api.folio.no/v2`)

---

## 1. Summary

The Liquidity Forecaster is a cash-position projection and early-warning tool
built on top of the Folio banking API. It pulls current balances across the
company's **Operational**, **Tax**, **Earmark** and **Savings** accounts, layers
in the historical balance trend and any scheduled future payments, and projects
the cash position several weeks forward.

Its primary job is to **alert before operational cash drops below a floor** the
user sets. This matters for a business (ChenMedia) with lumpy, seasonal cash
flows — festival and wedding work produces large, irregular inflows and outflows
whose timing does not line up neatly with payroll, tax, and supplier obligations.

---

## 2. Goals & non-goals

### Goals
- **G1.** Show the current, consolidated cash position across all non-card accounts.
- **G2.** Reconstruct the recent balance trend (per account) to ground the forecast in real run-rate behaviour.
- **G3.** Incorporate known, scheduled future payments (committed outflows) into the projection.
- **G4.** Project the operational cash position day-by-day for a configurable horizon (default: 8 weeks).
- **G5.** Raise an alert whenever the projected operational balance is expected to fall below a user-defined floor, with enough lead time to act.
- **G6.** Make the lumpiness visible — surface the specific large payments/dates that drive a dip.

### Non-goals (v1)
- **NG1.** Initiating, approving, or modifying payments. The forecaster is **read-only** against money movement. (`POST /payments`, `DELETE /payments/{id}`, `PATCH /events` are out of scope.)
- **NG2.** Full double-entry accounting, VAT/ledger categorisation, or bookkeeping. Folio/the accounting system owns that.
- **NG3.** Multi-currency portfolio optimisation. We track FX exposure only as a risk note (see [Alerting §4.6](04-alerting.md#46-fx-risk-note)).
- **NG4.** Predicting *unknown* future inflows from first principles (no ML revenue model in v1; we use simple trend + known scheduled items).

---

## 3. Users & key scenarios

**Primary user:** Owner/finance lead at a small media company (festivals, weddings).

- **S1 — "Can I make payroll?"** It's the 20th. Two festival invoices are still
  unpaid by clients, and a large supplier payment is scheduled for the 25th. Will
  operational cash stay above my floor through month-end?
- **S2 — "When does it get tight?"** Show me the next 8 weeks and highlight the
  days where I dip closest to (or below) the floor, and *which* payments cause it.
- **S3 — "Warn me early."** Don't make me check. If the projection crosses the
  floor within the horizon, notify me with the date, the shortfall amount, and the
  drivers.
- **S4 — "Where's my buffer?"** I keep Tax and Earmark money separate on purpose.
  Show me operational liquidity *excluding* ring-fenced funds, but let me see the
  total too.

---

**Next:** [02 · Data & accounts →](02-data-and-accounts.md)
