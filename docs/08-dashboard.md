# 08 · Web dashboard (Next.js + Clerk + Neon on Vercel)

**Part of the [Liquidity Forecaster spec](../README.md).**

A per-user authenticated dashboard for the forecast — severity, the projected balance
curve, trough, drivers, and expected inflows. Sign-in is via **Clerk**, restricted to
**@chenmedia.no** emails. The dashboard reads the latest forecast from **Neon (Postgres)**,
published by the scheduled job — so Vercel runs a **single runtime (Next.js only)**.

**Live URL:** <https://liquidity-forecaster-mauve.vercel.app> (the Vercel project's
production domain — we keep using this `.vercel.app` subdomain; no custom domain). Add
this origin to the **Clerk Dashboard → allowed origins / redirect URLs** so sign-in works
there.

## Architecture

```
Scheduled GitHub Action (Python)               Vercel (Next.js only)
  forecast run ──▶ publish_snapshot ──▶  Neon Postgres  ◀── app/api/forecast/route.ts
  (Slack/email alert too)                (forecast_snapshot)     · auth() (Clerk)
                                                                 · @chenmedia.no check
                                                                 · read latest snapshot
                                                                        ▲
                                                                Browser (Clerk session)
```

- **Python** computes the forecast (already the authoritative path) and writes a JSON
  snapshot to Neon (`publish.py`). The dashboard never computes — it **reads** the snapshot.
- **No Python on Vercel**: the previous serverless Python function is gone, which removes
  the Next.js/Python build conflict and gives real persistence.

## Security

- **Auth:** Clerk. `middleware.ts` requires a session for everything except sign-in/up.
- **Whitelist (two layers):** Clerk Dashboard → **Restrictions** allow only `chenmedia.no`
  (primary), and `app/api/forecast/route.ts` re-checks the email domain (`lib/access.ts`,
  unit-tested) → `403` otherwise.
- Security headers + Clerk-compatible CSP in `next.config.mjs`; API responses `no-store`;
  app is `noindex`. Read-only — the dashboard never triggers payments, alerts, or compute.

## Deploy

1. **Clerk app** (clerk.com) → Restrictions allow only `chenmedia.no`. Copy the keys.
2. **Neon database** (via the Vercel integration or neon.tech) → it provides a
   `DATABASE_URL`.
3. **Vercel** (framework auto-detected as Next.js) env vars:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` — from Clerk.
   - `DATABASE_URL` — from Neon.
   - Optional: `DASHBOARD_ALLOWED_EMAIL_DOMAIN` (default `chenmedia.no`).
4. **GitHub Actions** secret `DATABASE_URL` (same Neon string) so the scheduled run can
   publish. Plus the existing `FOLIO_API_KEY` etc.
5. **Seed the first snapshot:** trigger the `Liquidity forecast` workflow once (or run
   `python -m liquidity_forecaster publish` with `DATABASE_URL` + `FOLIO_API_KEY` set).
6. Open the Vercel URL, sign in with a @chenmedia.no email.

## How it refreshes

The dashboard shows the **last published snapshot**. It refreshes each scheduled run
(daily) and whenever you run `publish` / dispatch the workflow. The `forecast_snapshot`
table keeps the most recent ~30 rows (dashboard reads the latest).

## Develop locally

```bash
npm install
npm run dev        # Next.js (needs Clerk envs + DATABASE_URL)
npm test           # vitest (email allowlist)
npm run typecheck  # tsc --noEmit
```

Python engine + publisher: `pytest -q`, `ruff`, `mypy` (see [CONTRIBUTING](../CONTRIBUTING.md)).

## Notes & limits
- The dashboard is a **view** of the latest scheduled forecast, not an on-demand compute.
  The authoritative alerting path is unchanged.
- For a production Clerk instance on a custom domain, add that Clerk Frontend API host to
  the CSP in `next.config.mjs` (the dev CSP allows `*.clerk.accounts.dev`).

---

**Prev:** [← 07 · Roadmap](07-roadmap.md) · **Up:** [README](../README.md)
