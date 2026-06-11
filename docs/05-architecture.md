# 05 · Architecture

**Part of the [Liquidity Forecaster spec](../README.md).**

---

## 1. Components (proposed)

```
            ┌─────────────────────────┐
  schedule  │   Forecaster job        │
  (daily) ─▶│  1. fetch accounts      │──▶ Folio API v2 (Bearer key)
            │  2. sync balance history│
            │  3. fetch payments(→+8w)│
            │  4. build projection    │
            │  5. evaluate floor      │
            │  6. notify on change    │──▶ Slack #finance (webhook / bot token)
            │                         │··▶ Email fallback (on Slack failure)
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
- **Secrets.** API key, Slack webhook/token, and SMTP creds come from the
  environment / a secret store — **never committed**. See [Security §2](06-security.md).

### Suggested implementation
- Language: Python or TypeScript (either fits; pick per team familiarity).
- Money: decimal/fixed-point library — **never floats**.
- Persistence: SQLite (or flat JSON) for the cache + alert-state table.
- Scheduling: cron / scheduled CI job / serverless timer.

---

## 2. Data model (local store)

```
account            (account_number PK, name, type, current_balance,
                    balance_updated_at, matching_transactions_at, fetched_at)

daily_balance      (account_number, date, incoming_balance, outgoing_balance,
                    PRIMARY KEY (account_number, date))   # immutable past

scheduled_payment  (id PK, event_id, debtor_account_number, execution_date,
                    amount, currency, creditor_name, state, fetched_at)

config             (operational_floor, warning_band_pct, horizon_days,
                    lookback_days, include_drafts BOOL, base_currency='NOK',
                    slack_target='#finance', trough_change_delta_pct=5,
                    fallback_email='kai@chenmedia.no')
                    # slack_webhook_url / slack_bot_token / smtp creds come from
                    # secrets, NOT this table

alert_state        (date, level, trough_date, trough_balance, breach_first_date,
                    notified_at, delivered_via)   # for state-change-only notifications
```

> `scheduled_payment.creditor_name` and account numbers are **personal/financial
> data** — see the data-minimization and retention rules in
> [Security §5](06-security.md).

---

## 3. Edge cases & data-quality rules

- **Stale balance.** If `balanceUpdatedAt` is old or `matchingTransactionsAt` lags
  far behind today, flag the forecast as low-confidence (pending transactions not
  yet reflected). This confidence flag appears in the alert footer (§4.4).
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

**Prev:** [← 04 · Alerting](04-alerting.md) · **Next:** [06 · Security & privacy →](06-security.md)
