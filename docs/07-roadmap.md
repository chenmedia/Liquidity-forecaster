# 07 · Roadmap, acceptance criteria & open questions

**Part of the [Liquidity Forecaster spec](../README.md).**

---

## 1. Milestones

- **M0 — Read-only pull (this spec + spike).** Authenticate, fetch `/accounts`,
  list balances by bucket. ✅ understanding of API complete.
- **M1 — History sync + cache.** Backfill `daily_balance`, incremental refresh.
- **M2 — Projection engine.** Scheduled payments + current balance → daily curve;
  committed/draft scenarios.
- **M3 — Floor & Slack alerts.** Floor config, RED/AMBER/GREEN, Block Kit message to
  `#finance`, Slack webhook delivery, state-change-only send rule
  ([§4.4](04-alerting.md#44-slack-delivery-details)), and email fallback on Slack
  failure ([§4.5](04-alerting.md#45-email-fallback)).
- **M4 — Lumpiness UX.** Surface the drivers of each dip; "with reserves" view.
- **M5 — Phase 2.** Recurring baseline from history, `/events` enrichment, FX handling,
  extra notification channels.
- **Security gate (before any live run).** The
  [security checklist](06-security.md#security-checklist-pre-go-live) must pass.

---

## 2. Acceptance criteria

Checkable statements an implementation must satisfy. Several are anchored to the
[worked example](03-forecast.md#5-worked-example-v1-committed-scenario-baseline--0) as a
test fixture.

**Data & correctness**
- **AC-1.** Given the worked-example inputs, the projection produces a trough of
  **90 000 NOK on 2026-06-25**. *(verifies scheduling, sign handling, day placement)*
- **AC-2.** `Completed` payments are excluded and `InProcess` included — removing the
  `Completed` catering item leaves the curve unchanged; removing an `InProcess` item
  changes it. *(no double-counting)*
- **AC-3.** With `include_drafts=false` the employer-tax `Draft` is excluded; flipping
  to `true` lowers the 2026-06-25 trough by 95 000 to −5 000. *(scenario toggle)*
- **AC-4.** A `/payments` query whose `endDate` is left to default (today) is rejected
  by our client; the forecaster always sends `endDate ≥ horizon`. *(future-cutoff bug guard)*
- **AC-5.** Monetary values are parsed as fixed-point decimal; a float never appears in
  money math. *(precision)*

**Alerting**
- **AC-6.** The worked example yields **RED**, first-breach date 2026-06-15, shortfall
  **160 000 NOK** at the trough, and lists Sound & Light + Payroll as drivers.
- **AC-7.** "Draw on Savings clears it?" returns **yes** for the worked example
  (Savings 300 000 ≥ shortfall 160 000).
- **AC-8.** Any payment in `RetryingInsufficientFunds` forces RED regardless of projection.
- **AC-9.** Running twice with unchanged inputs sends **exactly one** alert (state-change
  rule); an unchanged amber on day 2 sends nothing.
- **AC-10.** When the Slack post fails after retries, the **email fallback** delivers the
  same alert, and `alert_state.delivered_via` records the fallback. No alert is lost.
- **AC-11.** A low-confidence forecast (stale `balanceUpdatedAt` /
  lagging `matchingTransactionsAt`) is flagged in the alert footer.

**Security** *(see [§6 checklist](06-security.md#security-checklist-pre-go-live))*
- **AC-12.** No secret is present in the repo or git history; secret scan passes in CI.
- **AC-13.** The app issues **no** calls to money-moving endpoints (verified by request log
  / allowlist test).
- **AC-14.** Logs contain no tokens, webhook URLs, or unmasked account numbers.

**Outcome (the "north star")**
- **AC-15.** For a sub-floor projection, the alert arrives with **≥ 5 business days**
  lead time before the breach date whenever the data allows.
- **AC-16.** The owner can answer "can I make payroll / this supplier run?" from a single
  alert/report without opening the bank.

---

## 3. Open questions

1. ~~**Notification channel(s)** for v1~~ — **Resolved:** Slack to the shared **`#finance`**
   channel (incoming webhook / bot token, state-change-only sends;
   [§4.3–4.4](04-alerting.md#43-delivery--cadence)), with an **email fallback** to the
   owner that fires only when Slack delivery fails
   ([§4.5](04-alerting.md#45-email-fallback)).
2. **Default floor & horizon** — proposed defaults are in
   [§4.1](04-alerting.md#41-floor--defaults) (floor 250 000 NOK, band 25%, horizon 8
   weeks) but are **placeholders to confirm** against ChenMedia's actual payroll/tax run.
3. **Recurring baseline in v1?** Current plan: ship v1 with baseline = 0 (conservative,
   scheduled-only) and add the trend-derived run-rate
   ([§4 phase 2](03-forecast.md#4-recurring-baseline--double-count-avoidance-phase-2)) later.
4. **Auth model** — personal API key (`api-tilgang`) vs company OAuth2 flow? Affects
   refresh-token handling ([Security §9](06-security.md#9-auth-lifecycle)) and which
   accounts are visible.
5. **Inflow forecasting** — do we model expected client payments (festival/wedding
   invoices) at all in v1, or only count money already scheduled in Folio?

---

**Prev:** [← 06 · Security & privacy](06-security.md) · **Up:** [README](../README.md)
