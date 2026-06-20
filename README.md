# Liquidity Forecaster

A cash-position projection and early-warning tool for **ChenMedia**, built on the
[Folio](https://folio.no) banking API. It pulls current balances across the
Operational, Tax, Earmark and Savings accounts, layers in the historical balance
trend and any scheduled future payments, and projects the cash position several
weeks out — then **alerts in Slack before operational cash drops below a floor**
you set. This matters when festival and wedding work makes inflows and outflows
large and lumpy.

> **Status:** v1 implementation in progress — spec complete, Python forecaster
> (milestones M1–M3) landing.
> **Owner:** kai@chenmedia.no · **Last updated:** 2026-06-10

---

## Documentation

The specification is split into focused documents under [`docs/`](docs/):

| # | Document | Contents |
|---|----------|----------|
| 01 | [Overview](docs/01-overview.md) | Summary, goals & non-goals, users & scenarios |
| 02 | [Data & accounts](docs/02-data-and-accounts.md) | Account model, Folio data sources, retrieval strategy |
| 03 | [Forecast](docs/03-forecast.md) | Projection model, recurring baseline, worked example |
| 04 | [Alerting](docs/04-alerting.md) | Floor & defaults, RED/AMBER/GREEN, Slack, email fallback, FX |
| 05 | [Architecture](docs/05-architecture.md) | Components, local data model, edge cases |
| 06 | [Security & privacy](docs/06-security.md) | Threat model, secrets, data protection, GDPR |
| 07 | [Roadmap](docs/07-roadmap.md) | Milestones, acceptance criteria, open questions |
| 08 | [Web dashboard](docs/08-dashboard.md) | Vercel deploy: serverless API + dashboard, auth |

Supporting docs: [`docs/SECRETS.md`](docs/SECRETS.md) (how to supply credentials
safely) and the vendored Folio OpenAPI definition in
[`reference/folio-api.json`](reference/folio-api.json).

---

## At a glance

- **Read-only** against money movement — it never initiates or modifies payments.
- **Poll-based** — the Folio API has no webhooks; the forecaster runs on a schedule.
- **Slack-first alerting** to `#finance`, with an **email fallback** if Slack delivery fails.
- **Layered projection** — current balance + scheduled payments, plus (optional) a
  recurring run-rate baseline from history, expected client inflows, and FX-converted
  foreign payments.

## Running it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # or just -e . for runtime only

export FOLIO_API_KEY=…             # from a secret store, never committed (docs/SECRETS.md)

python -m liquidity_forecaster accounts        # print balances by bucket (read-only)
python -m liquidity_forecaster run --dry-run    # project + show the alert without sending
python -m liquidity_forecaster run              # send to Slack #finance (email fallback)
python -m liquidity_forecaster send-test        # post a sample alert to verify the webhook
python -m liquidity_forecaster sync-history     # backfill cached daily balances (phase 2)
```

Run `run --scenario drafts` to include `Draft` payments (pessimistic). On a schedule,
the [`forecast.yml`](.github/workflows/forecast.yml) GitHub Actions workflow runs it
daily once the repo secrets are set; it skips cleanly until then. If you run several
Operational accounts, set `FOLIO_OPERATIONAL_ACCOUNT` to pick which one to forecast.

**Develop:** `pytest -q`, `ruff check src tests`, `mypy src`. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Go-live checklist

1. Merge PR #1 (spec) → `main`, then PR #2 (code) → `main`.
2. **Rotate** the Folio API key; create a Slack **incoming webhook** for `#finance`.
3. Add GitHub **Actions secrets** (`FOLIO_API_KEY`, `SLACK_WEBHOOK_URL`, optional `SMTP_*`)
   and **variables** (`FORECAST_FLOOR`, `SLACK_CHANNEL`, `FOLIO_OPERATIONAL_ACCOUNT` if
   needed) — see [`docs/SECRETS.md`](docs/SECRETS.md).
4. Verify the channel: `send-test`. Then sanity-check live data: `accounts`, `run --dry-run`.
5. Confirm the floor against real balances; let the daily workflow run.
6. *(Optional)* require **CI** + **Secret scan** as status checks on `main`.

## Security

This tool handles live banking credentials and financial data. Security
requirements (secrets management, least-privilege, data protection, logging
redaction, dependency hygiene, GDPR) are specified in
[`docs/06-security.md`](docs/06-security.md) and must be met by any implementation.
The repository ships a [`.gitignore`](.gitignore) that blocks secrets, local
databases, and environment files from ever being committed, plus **gitleaks
secret scanning** as a pre-commit hook and a CI backstop (see
[`docs/SECRETS.md`](docs/SECRETS.md)).

## Repository layout

```
.
├── README.md                  # this file
├── pyproject.toml             # package, deps, ruff/mypy/pytest config
├── .gitignore                 # blocks secrets / db / env from commits
├── src/liquidity_forecaster/  # the application
│   ├── config.py  money.py  models.py  folio_client.py
│   ├── forecast.py  alerting.py  store.py  pipeline.py  cli.py
│   └── notify/                # slack.py, email_fallback.py, message.py
├── tests/                     # acceptance tests + fixtures
├── app/                       # Next.js dashboard (Clerk auth, App Router)
├── lib/access.ts  lib/db.ts   # email allowlist + Neon snapshot read
├── middleware.ts              # Clerk route protection
├── next.config.mjs package.json   # web app config
├── docs/                      # the specification, split by concern (01..08, SECRETS)
├── reference/folio-api.json   # vendored Folio OpenAPI v2 definition
└── .github/workflows/         # ci.yml, secret-scan.yml, forecast.yml (scheduled)
```

## Web dashboard

A read-only **Next.js** dashboard (severity, projected curve, trough, drivers, inflows)
on **Vercel**, with **Clerk** sign-in restricted to **@chenmedia.no**. The scheduled job
publishes the forecast to **Neon (Postgres)** and the dashboard reads it — single runtime,
no Python on Vercel.

**Live at <https://liquidity-forecaster-mauve.vercel.app>.** See
[`docs/08-dashboard.md`](docs/08-dashboard.md).
