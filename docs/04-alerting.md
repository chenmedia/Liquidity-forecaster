# 04 · Alerting

**Part of the [Liquidity Forecaster spec](../README.md).**

---

## 4.1 Floor & defaults
- User sets an **operational cash floor** — the minimum operational balance they're
  willing to hit.
- A **warning band** above the floor produces the early "amber" alert.

**Proposed v1 defaults** (⚠️ placeholders for kai@ to confirm against real numbers —
the floor should be sized to cover the biggest near-term fixed obligation, typically
one payroll + tax run):

| Setting | Default | Rationale |
|---|---|---|
| `operational_floor` | **250 000 NOK** | ~one month of payroll + employer tax buffer; tune to actual payroll. |
| `warning_band_pct` | **25%** | Amber when projected ≤ 312 500 NOK (floor × 1.25) → early nudge before RED. |
| `horizon_days` | **56 (8 weeks)** | Covers two payroll/tax cycles and typical festival/wedding payment lead times. |
| `lookback_days` | **90** | Enough history for a stable weekday run-rate without over-weighting stale seasons. |
| `trough_change_delta_pct` | **5%** | Re-notify only when an unchanged-severity trough worsens ≥ 5%. |
| `include_drafts` | **false** | Default to committed-only; user can switch to the pessimistic view. |

> These are starting points, **not** validated against ChenMedia's actuals. First run
> should print the current balances so the owner can right-size the floor before
> enabling alerts.

## 4.2 Trigger logic
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

## 4.3 Delivery & cadence
- Run on a schedule (e.g. daily each morning) — no webhooks in the Folio API, so
  the forecaster **polls**.
- Notify only on **state change** or **new/worsened breach** to avoid alert fatigue
  (don't re-send the same amber every day). See §4.4 for the exact send rule.
- **Channel (v1): Slack** to `#finance`, with an **email fallback** (§4.5) on Slack
  failure. Phase 2 may add calendar or always-on email mirroring.

## 4.4 Slack delivery details
- **Target:** the shared **`#finance`** Slack channel (not a DM) — keeps the owner
  and anyone else with finance responsibility in the loop.
- **Transport:** Slack Incoming Webhook URL (or a bot token + `chat.postMessage`),
  stored as a secret (`SLACK_WEBHOOK_URL` / `SLACK_BOT_TOKEN`) — never committed
  (see [Security](06-security.md)). *(No Slack integration is wired up yet — this is a
  v1 build dependency.)*
- **Message format:** Block Kit message with:
  - Header line with severity emoji — 🔴 RED / 🟡 AMBER / 🟢 GREEN (green only on
    recovery, see send rule).
  - One-line summary: first breach date, projected trough balance, shortfall vs floor,
    and lead time in business days.
  - A short list of the **driver payments** (date · creditor · amount) causing the dip.
  - A "draw on Savings clears it?" yes/no line.
  - Footer: forecast run timestamp + data-confidence flag (see
    [Architecture §3 staleness rule](05-architecture.md#3-edge-cases--data-quality-rules)).
- **Send rule (state-change-only):** compare against `alert_state` from the last run.
  Send when:
  - severity **worsens** (GREEN→AMBER, AMBER→RED, or GREEN→RED), **or**
  - severity is unchanged but the **trough balance drops materially** (configurable
    delta, default ≥ 5%) or the **breach date moves earlier**, **or**
  - severity **recovers** to GREEN (send one "all clear"), **or**
  - any payment enters `RetryingInsufficientFunds` (always send, RED — see §4.2).
  Otherwise **stay silent** (no daily repeat of an unchanged amber).
- **Threading (optional, phase 2):** keep one Slack thread per ongoing breach so
  follow-up updates reply in-thread rather than spawning new top-level messages.
- **Failure handling:** if the Slack post fails, retry with backoff (e.g. 3 attempts).
  If still failing, fall back to email (§4.5) and record the gap in `alert_state` so
  the next successful Slack run reports it (never silently drop a RED).

## 4.5 Email fallback
Email is a **fallback only** — it fires when Slack delivery cannot be confirmed, so a
breach alert is never lost because Slack is down or misconfigured.

- **Trigger:** Slack post fails after all retries (network error, bad webhook, 4xx/5xx).
  Not sent when Slack succeeds (no double-notify).
- **Recipient:** the owner (`kai@chenmedia.no`); recipient list configurable.
- **Transport:** Gmail or SMTP; sender/credentials from secrets (see [Security](06-security.md)).
- **Content:** the same payload as the Slack message (severity, first breach date,
  trough balance, shortfall, lead time, driver payments, "draw on Savings?" line,
  confidence flag), rendered as text/HTML instead of Block Kit. Subject encodes
  severity, e.g. `[RED] Operational cash below floor on 2026-07-02 — shortfall 84 000 NOK`.
- **Dedup:** the email obeys the same state-change-only rule (§4.4) — it represents the
  *same* alert that failed to reach Slack, not an independent channel that re-notifies.
- **Recovery:** once Slack delivery succeeds again, the next run posts a short note that
  earlier alert(s) were delivered via email fallback during the outage.

> **Tunable:** if the owner later wants email to *always* mirror RED alerts (belt-and-
> suspenders for the most severe case) rather than only on Slack failure, that is a
> one-line change to the send rule.

## 4.6 FX risk note
Payments may be foreign (`currencyAmount.currency` ≠ NOK, with `foreignPaymentInfo`).
For non-NOK scheduled outflows, the NOK debit isn't fixed until execution. v1 flags
these as **FX-variable** and projects at a conservative/current rate; it does not
hedge or optimise.

---

**Prev:** [← 03 · Forecast](03-forecast.md) · **Next:** [05 · Architecture →](05-architecture.md)
