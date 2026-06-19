# 08 · Web dashboard (Next.js + Clerk on Vercel)

**Part of the [Liquidity Forecaster spec](../README.md).**

A per-user authenticated dashboard for the forecast — severity, the projected balance
curve, trough, drivers, and expected inflows. Sign-in is via **Clerk**, restricted to
**@chenmedia.no** emails. The tested Python forecast engine is reused as an internal
compute service (no logic is duplicated in TypeScript).

## Architecture

```
Browser ──(Clerk session)──▶ Next.js (App Router, @clerk/nextjs)
                              · middleware.ts protects all routes
                              · app/page.tsx renders the dashboard
                              ▼
                    app/api/forecast/route.ts (server)
                      · auth() requires a signed-in user
                      · currentUser() email must be @chenmedia.no  (lib/access.ts)
                      · calls /api/compute with INTERNAL_API_SECRET
                              ▼
                    api/compute.py (Python serverless, INTERNAL only)
                      · rejects unless X-Internal-Secret matches
                      · pipeline.compute_forecast + serialize.forecast_to_dict
```

The browser never calls the Python function; all user auth lives in Next.js/Clerk, and
the Python function is gated by a server-only secret.

## Security

- **Auth:** Clerk. `middleware.ts` (`clerkMiddleware`) requires a session for everything
  except `/sign-in`, `/sign-up`, `/access-denied`.
- **Whitelist:** two layers — set the **Clerk Dashboard → Restrictions** to allow only
  the `chenmedia.no` domain (primary), and the API route re-checks the user's email
  domain (`isAllowedEmail`, unit-tested) as defense in depth → `403` otherwise.
- **Internal function:** `api/compute.py` requires `X-Internal-Secret` ==
  `INTERNAL_API_SECRET` (constant-time), **fails closed** if unset. Only the Next.js
  server sends it.
- Security headers + a Clerk-compatible CSP are set in `next.config.mjs`; API responses
  are `no-store`; the app is `noindex`. Read-only — never triggers payments or alerts.

## Deploy

1. **Create a Clerk application** (clerk.com). Under **Restrictions**, allow only the
   `chenmedia.no` email domain. Copy the **Publishable** and **Secret** keys.
2. **Import the repo into Vercel** (framework auto-detected as Next.js). The Python
   function under `api/` is built alongside it.
3. **Environment variables** (Project → Settings):
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` — from Clerk.
   - `INTERNAL_API_SECRET` — `openssl rand -hex 32`.
   - `FOLIO_API_KEY` — Folio read access.
   - `FORECAST_DB_PATH=/tmp/forecaster.db` (serverless FS is read-only except `/tmp`).
   - Optional: `DASHBOARD_ALLOWED_EMAIL_DOMAIN` (default `chenmedia.no`), `FORECAST_FLOOR`,
     `FOLIO_OPERATIONAL_ACCOUNT`, `FX_RATES`, `EXPECTED_INFLOWS_FILE`.
4. **Deploy**, open the URL, sign in with a @chenmedia.no email.

## Develop locally

```bash
npm install
npm run dev           # Next.js dev server (needs the Clerk + INTERNAL_API_SECRET envs)
npm test              # vitest (access allowlist)
npm run typecheck     # tsc --noEmit
```

The Python engine and its tests are unchanged: `pytest -q`, `ruff`, `mypy` (see
[CONTRIBUTING](../CONTRIBUTING.md)).

## Notes & limits

- **No persistent history on Vercel** (read-only FS) → the run-rate baseline is
  effectively off there. The authoritative alerting (cached state + history) stays the
  scheduled GitHub Actions run; the dashboard is a *view*.
- For a production Clerk instance on a custom domain, add that Clerk Frontend API host to
  the CSP in `next.config.mjs` (the dev CSP allows `*.clerk.accounts.dev`).

---

**Prev:** [← 07 · Roadmap](07-roadmap.md) · **Up:** [README](../README.md)
