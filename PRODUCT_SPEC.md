# Liquidity Forecaster — Product Specification

**Status:** Draft v1
**Owner:** kai@chenmedia.no
**Last updated:** 2026-06-10
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
- **NG3.** Multi-currency portfolio optimisation. We track FX exposure only as a risk note (see §7.4).
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

## 4. Account model (from Folio `GET /accounts`)

Accounts are returned with a `type` enum: `Card`, `Earmarks`, `Operational`,
`Tax`, `Savings`. Each account carries:

| Field | Meaning | Use in forecaster |
|---|---|---|
| `accountNumber` | Account identifier (BBAN) | Key for per-account history/transactions |
| `balance` | Current balance (string decimal, NOK) | Forecast starting point |
| `balanceUpdatedAt` | Last time balance changed | Freshness check |
| `matchingTransactionsAt` | Last date balance matches transactions (no pending data) | Confidence boundary — data before this is settled |
| `completeTransactionsAt` | Last date all transactions are fully documented | Informational |
| `name` | Descriptive name | Display |
| `type` | Account class | Bucketing (see below) |

### Account bucketing
- **Operational** — the account the floor and alerts are primarily about. This is "can I run the business" money.
- **Tax** — ring-fenced for VAT/employer tax. Treated as **not available** for operational liquidity by default (it's owed to the state).
- **Earmarks** — funds reserved for a specific purpose. **Not available** by default.
- **Savings** — buffer. Counted as *available reserve* but shown separately from operational cash; optionally drawn down in a "with reserves" view.
- **Card** — excluded from the liquidity projection (spending instrument, not a cash pool), but its activity shows up as operational outflows.

> **Design note:** the floor/alert logic runs on **Operational** balance by
> default. We also compute "Operational + Savings" (available liquidity) as a
> secondary line so the user can see how much runway the buffer adds.

---

## 5. Data sources & retrieval strategy

All calls authenticate with a bearer API key (`Authorization: Bearer <token>`).
Amounts are NOK strings; parse to fixed-point decimal (never float) for money math.

### 5.1 Current balances — `GET /accounts`
Single call. Provides the forecast's "today" anchor for each account, plus the
freshness/settlement timestamps used for confidence.

### 5.2 Historical balance trend — `GET /accounts/{accountNumber}/balance/{date}`
Returns `incomingBalance` (start of day) and `outgoingBalance` (end of day) for
one date. To build a trend we call this **per account, per date** over a lookback
window (default 90 days).

- **Cost:** N_accounts × N_days calls. With 4 accounts × 90 days = 360 calls per
  full rebuild. → **Must be cached** and refreshed incrementally (only fetch dates
  not already stored; historical days are immutable once `matchingTransactionsAt`
  has passed them).
- Daily net flow for a date = `outgoingBalance − incomingBalance`.
- Missing `incomingBalance`/`outgoingBalance` ⇒ account wasn't open that day; skip.

### 5.3 Scheduled future payments — `GET /payments?startDate&endDate`
This is the committed-outflow backbone of the forecast.

- **Critical:** `endDate` defaults to *today*. To capture **future** scheduled
  payments we must pass an explicit `endDate` at/after the forecast horizon
  (e.g. today + 8 weeks). `startDate` = today.
- Each `Payment` has `executionDate`, `currencyAmount`, `creditor`,
  `debtorAccountNumber`, and a `state`:

  | `state` | Treatment in forecast |
  |---|---|
  | `Draft` | Not yet submitted to bank. Include as **tentative** (toggleable); may not happen. |
  | `InProcess` | Approved & accepted for execution → include as **committed** outflow. |
  | `RetryingInsufficientFunds` | Active but already failing for lack of funds → **committed + red flag** (we're already short). |
  | `Completed` | Already reflected in balance → **exclude** (avoid double-count). |
  | `Cancelled` | **Exclude.** |
  | `Rejected` | **Exclude** from projection, but **surface** — a rejected obligation often still needs paying. |

- `debtorAccountNumber` tells us *which* account the outflow hits → apply to the
  right bucket (operational dips when operational is the debtor).

### 5.4 Future events (optional enrichment) — `GET /events?startDate&endDate`
Events are "anything that is or will end up as a transaction." This can surface
expected items beyond formal payments. v1 treats `/payments` as the source of
truth for committed outflows; `/events` is a **phase-2 enrichment** to catch
future inflows/outflows not represented as payments. Same `endDate`-defaults-to-today
caveat applies.

### 5.5 Realized history (optional) — `GET /accounts/{accountNumber}/transactions`
Used to characterise the *recurring baseline* (rent, payroll, subscriptions) and
to estimate a recurring run-rate for days with no scheduled payments. Phase 2.

---

## 6. Forecast methodology

### 6.1 Model (v1 — deterministic baseline)
For each account, projected balance on day *d*:

```
balance(d) = balance(today)
           + Σ scheduled_inflows(today..d)      // from /payments, /events
           − Σ scheduled_outflows(today..d)      // committed payments by executionDate
           + recurring_baseline(today..d)        // est. from historical trend (phase 2)
```

- **Day 0** = current `balance` from `GET /accounts`.
- **Scheduled items** are placed on their `executionDate`.
- **Recurring baseline** (phase 2): a per-weekday/per-month average daily net flow
  derived from §5.2 history, *excluding* the large lumpy items already captured as
  scheduled payments (to avoid double counting). v1 can run with baseline = 0 and
  rely purely on scheduled items + current balance for a conservative projection.

### 6.2 Horizon & granularity
- Default horizon: **8 weeks (56 days)**, configurable.
- Granularity: **daily**. Alerting evaluates the daily minimum.

### 6.3 Scenarios
- **Committed** (default): only `InProcess` + `RetryingInsufficientFunds` outflows.
- **Committed + Drafts**: adds `Draft` payments (pessimistic on outflow).
- **With reserves**: operational + savings line, to show buffered runway.

### 6.4 Output of a forecast run
- Per-day projected balance for Operational (and Operational+Savings).
- The list of scheduled items driving each day's change.
- Identified **risk dates**: days where projected balance < floor.
- Headroom: `min(projected balance over horizon) − floor`.

---

## 7. Alerting

### 7.1 Floor
- User sets an **operational cash floor** (e.g. 200 000 NOK) — the minimum
  operational balance they're willing to hit.
- Optional **warning band** above the floor (e.g. floor + 20%) for an early "amber" alert.

### 7.2 Trigger logic
On each forecast run, evaluate the projected Operational balance across the horizon:
- **RED** — projected balance < floor on any day within the horizon.
- **AMBER** — projected balance < (floor + warning band) but ≥ floor.
- **GREEN** — stays above the warning band throughout.

An alert fires (RED/AMBER) and includes:
- First date the threshold is breached (lead time = that date − today).
- Projected balance and shortfall at the trough.
- The specific scheduled payments contributing to the dip (date, creditor, amount).
- Whether drawing on Savings would clear it.

Special case: any payment already in `RetryingInsufficientFunds` ⇒ immediate
**RED**, regardless of projection (we're short *now*).

### 7.3 Delivery & cadence
- Run on a schedule (e.g. daily each morning) — no webhooks in the Folio API, so
  the forecaster **polls**.
- Notify only on **state change** or **new/worsened breach** to avoid alert fatigue
  (don't re-send the same amber every day). See §7.5 for the exact send rule.
- **Channel (v1): Slack.** Alerts post to a configured Slack channel/DM via an
  **incoming webhook** (or bot token). Phase 2 may add email/calendar.

### 7.5 Slack delivery details
- **Transport:** Slack Incoming Webhook URL (or a bot token + `chat.postMessage`),
  stored as a secret (`SLACK_WEBHOOK_URL` / `SLACK_BOT_TOKEN`) — never committed.
  *(No Slack MCP/integration is wired up yet — this is a v1 build dependency.)*
- **Message format:** Block Kit message with:
  - Header line with severity emoji — 🔴 RED / 🟡 AMBER / 🟢 GREEN (green only on
    recovery, see send rule).
  - One-line summary: first breach date, projected trough balance, shortfall vs floor,
    and lead time in business days.
  - A short list of the **driver payments** (date · creditor · amount) causing the dip.
  - A "draw on Savings clears it?" yes/no line.
  - Footer: forecast run timestamp + data-confidence flag (see §10 staleness rule).
- **Send rule (state-change-only):** compare against `alert_state` from the last run.
  Send when:
  - severity **worsens** (GREEN→AMBER, AMBER→RED, or GREEN→RED), **or**
  - severity is unchanged but the **trough balance drops materially** (configurable
    delta, default ≥ 5%) or the **breach date moves earlier**, **or**
  - severity **recovers** to GREEN (send one "all clear"), **or**
  - any payment enters `RetryingInsufficientFunds` (always send, RED — see §7.2).
  Otherwise **stay silent** (no daily repeat of an unchanged amber).
- **Threading (optional, phase 2):** keep one Slack thread per ongoing breach so
  follow-up updates reply in-thread rather than spawning new top-level messages.
- **Failure handling:** if the Slack post fails, retry with backoff; if still failing,
  record it so the next successful run reports the gap (never silently drop a RED).

### 7.4 FX risk note
Payments may be foreign (`currencyAmount.currency` ≠ NOK, with `foreignPaymentInfo`).
For non-NOK scheduled outflows, the NOK debit isn't fixed until execution. v1 flags
these as **FX-variable** and projects at a conservative/current rate; it does not
hedge or optimise.

---

## 8. Architecture (proposed)

```
            ┌─────────────────────────┐
  schedule  │   Forecaster job        │
  (daily) ─▶│  1. fetch accounts      │──▶ Folio API v2 (Bearer key)
            │  2. sync balance history│
            │  3. fetch payments(→+8w)│
            │  4. build projection    │
            │  5. evaluate floor      │
            │  6. notify on change    │──▶ Slack (incoming webhook / bot token)
            └───────────┬─────────────┘
                        │
              ┌─────────▼─────────┐
              │  Local store      │  (cached daily balances [immutable past],
              │  (sqlite/json)    │   last alert state, config: floor/horizon)
              └───────────────────┘
```

- **Stateless compute, cached data.** Historical daily balances are immutable
  once settled (`matchingTransactionsAt` passed) → cache aggressively, fetch only
  missing dates.
- **Idempotent runs.** A run recomputes from cache + a small set of fresh calls
  (`/accounts`, future `/payments`). Safe to re-run.
- **Secrets.** API key from environment/secret store, never committed.

### Suggested implementation
- Language: Python or TypeScript (either fits; pick per team familiarity).
- Money: decimal/fixed-point library — **never floats**.
- Persistence: SQLite (or flat JSON) for the cache + alert-state table.
- Scheduling: cron / scheduled CI job / serverless timer.

---

## 9. Data model (local store)

```
account            (account_number PK, name, type, current_balance,
                    balance_updated_at, matching_transactions_at, fetched_at)

daily_balance      (account_number, date, incoming_balance, outgoing_balance,
                    PRIMARY KEY (account_number, date))   # immutable past

scheduled_payment  (id PK, event_id, debtor_account_number, execution_date,
                    amount, currency, creditor_name, state, fetched_at)

config             (operational_floor, warning_band_pct, horizon_days,
                    include_drafts BOOL, base_currency='NOK',
                    slack_target, trough_change_delta_pct=5)
                    # slack_webhook_url / slack_bot_token come from secrets, not here

alert_state        (date, level, trough_date, trough_balance, breach_first_date,
                    notified_at)   # for state-change-only notifications
```

---

## 10. Edge cases & data-quality rules

- **Stale balance.** If `balanceUpdatedAt` is old or `matchingTransactionsAt` lags
  far behind today, flag the forecast as low-confidence (pending transactions not
  yet reflected).
- **Double counting.** Exclude `Completed` payments — they're already in `balance`.
  Only count outflows with `executionDate ≥ today`.
- **Account not open on a date.** Missing `incoming/outgoingBalance` → skip that
  day in trend, don't treat as zero.
- **Decimal parsing.** `AccountBalance`/`Account.balance` allow variable decimals
  (`^\d+\.\d+$`); `TransactionAmount` is 2dp. Parse defensively into fixed-point.
- **Future payments cutoff.** Always set `endDate ≥ horizon` on `/payments` and
  `/events`; otherwise future-dated items are silently missed (endDate defaults to today).
- **Rejected obligations.** `Rejected` payments leave the projection but should be
  surfaced — the bill likely still needs paying and may re-enter as a new payment.
- **Rate limits / pagination.** History backfill is call-heavy; throttle and cache.
  Treat the API as poll-only (no streaming/webhooks).
- **Time zones.** `executionDate`/balance dates are calendar dates; pin everything
  to Europe/Oslo to avoid off-by-one day boundaries.

---

## 11. Open questions

1. ~~**Notification channel(s)** for v1~~ — **Resolved: Slack** (incoming webhook /
   bot token, state-change-only sends; see §7.3/§7.5). Open sub-question: post to a
   shared channel or DM the owner? And do we want phase-2 email as a fallback when
   Slack delivery fails?
2. **Default floor & horizon** values — what numbers does ChenMedia actually run with?
3. **Recurring baseline in v1?** Ship v1 with baseline = 0 (conservative, scheduled-only)
   and add the trend-derived run-rate in phase 2, or include it from the start?
4. **Auth model** — personal API key (`api-tilgang`) vs company OAuth2 flow? Affects
   refresh-token handling and which accounts are visible.
5. **Inflow forecasting** — do we model expected client payments (festival/wedding
   invoices) at all in v1, or only count money already scheduled in Folio?

---

## 12. Milestones

- **M0 — Read-only pull (this spec + spike).** Authenticate, fetch `/accounts`,
  list balances by bucket. ✅ understanding of API complete.
- **M1 — History sync + cache.** Backfill `daily_balance`, incremental refresh.
- **M2 — Projection engine.** Scheduled payments + current balance → daily curve;
  committed/draft scenarios.
- **M3 — Floor & Slack alerts.** Floor config, RED/AMBER/GREEN, Block Kit message,
  Slack webhook delivery, state-change-only send rule (§7.5).
- **M4 — Lumpiness UX.** Surface the drivers of each dip; "with reserves" view.
- **M5 — Phase 2.** Recurring baseline from history, `/events` enrichment, FX handling,
  extra notification channels.

---

## 13. Success criteria

- The forecaster reliably warns of a sub-floor operational balance **with enough
  lead time** to move money or chase an invoice (target: ≥ 5 business days).
- No false "all clear" caused by missed future-dated payments or double-counted
  completed ones.
- The owner can answer "can I make payroll / this supplier run?" in seconds without
  opening the bank.
