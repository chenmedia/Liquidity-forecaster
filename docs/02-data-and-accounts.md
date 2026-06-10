# 02 · Data & accounts

**Part of the [Liquidity Forecaster spec](../README.md).**
**Folio OpenAPI reference:** [`reference/folio-api.json`](../reference/folio-api.json)

---

## 1. Account model (from Folio `GET /accounts`)

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

## 2. Data sources & retrieval strategy

All calls authenticate with a bearer API key (`Authorization: Bearer <token>`).
Amounts are NOK strings; parse to fixed-point decimal (**never float**) for money math.
See [Security §3](06-security.md) for how the key is stored and handled.

### 2.1 Current balances — `GET /accounts`
Single call. Provides the forecast's "today" anchor for each account, plus the
freshness/settlement timestamps used for confidence.

### 2.2 Historical balance trend — `GET /accounts/{accountNumber}/balance/{date}`
Returns `incomingBalance` (start of day) and `outgoingBalance` (end of day) for
one date. To build a trend we call this **per account, per date** over a lookback
window (default 90 days).

- **Cost:** N_accounts × N_days calls. With 4 accounts × 90 days = 360 calls per
  full rebuild. → **Must be cached** and refreshed incrementally (only fetch dates
  not already stored; historical days are immutable once `matchingTransactionsAt`
  has passed them).
- Daily net flow for a date = `outgoingBalance − incomingBalance`.
- Missing `incomingBalance`/`outgoingBalance` ⇒ account wasn't open that day; skip.

### 2.3 Scheduled future payments — `GET /payments?startDate&endDate`
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

### 2.4 Future events (optional enrichment) — `GET /events?startDate&endDate`
Events are "anything that is or will end up as a transaction." This can surface
expected items beyond formal payments. v1 treats `/payments` as the source of
truth for committed outflows; `/events` is a **phase-2 enrichment** to catch
future inflows/outflows not represented as payments. Same `endDate`-defaults-to-today
caveat applies.

### 2.5 Realized history (optional) — `GET /accounts/{accountNumber}/transactions`
Used to characterise the *recurring baseline* (rent, payroll, subscriptions) and
to estimate a recurring run-rate for days with no scheduled payments. Phase 2 —
see [Forecast §4](03-forecast.md#4-recurring-baseline--double-count-avoidance-phase-2).

---

**Prev:** [← 01 · Overview](01-overview.md) · **Next:** [03 · Forecast →](03-forecast.md)
