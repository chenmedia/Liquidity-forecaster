# 08 · Web dashboard (Vercel)

**Part of the [Liquidity Forecaster spec](../README.md).**

A read-only web view of the current forecast — severity, the projected balance curve,
trough, drivers, and expected inflows — served on Vercel. It reuses the Python forecast
engine via a serverless function; there is no separate copy of the logic.

## Pieces

| File | Role |
|------|------|
| `index.html` | Static dashboard (vanilla JS, inline SVG chart — no third-party scripts) |
| `api/forecast.py` | Vercel Python serverless function → returns the forecast as JSON |
| `src/liquidity_forecaster/web.py` | Auth gate + payload builder (testable) |
| `src/liquidity_forecaster/serialize.py` | `Forecast` → JSON-friendly dict |
| `vercel.json` | Function `includeFiles` (bundles `src/`) + security headers |
| `requirements.txt` | Runtime deps for the function (httpx, pydantic) |

## Security

The dashboard exposes **live financial data**, so the API is gated by a shared secret:

- `GET /api/forecast` requires `DASHBOARD_TOKEN` via the `X-Dashboard-Token` header
  (or `?token=`). It **fails closed** — returns `503` if `DASHBOARD_TOKEN` is unset,
  `401` on a wrong/missing token. Token comparison is constant-time.
- The page prompts for the token and keeps it in `localStorage`; it's sent only to
  `/api/forecast` over HTTPS.
- Responses are `no-store`; a strict-ish CSP and `X-Frame-Options: DENY` are set in
  `vercel.json`. The page is `noindex`.
- This is a single-secret gate suitable for a small internal tool. For stronger control
  use Vercel's built-in **Password Protection / SSO** (Pro) in front of it.

> The token is **not** a substitute for `FOLIO_API_KEY` — it only guards the dashboard.

## Deploy

1. **Import the repo** into Vercel (Framework preset: **Other**). It auto-detects the
   static site + the `api/*.py` Python function.
2. **Set Environment Variables** (Project → Settings → Environment Variables):
   - `FOLIO_API_KEY` — Folio read access (same value as the GitHub Actions secret).
   - `DASHBOARD_TOKEN` — a strong random string you'll type into the dashboard.
   - `FORECAST_DB_PATH=/tmp/forecaster.db` — serverless filesystems are read-only except
     `/tmp`. (History/baseline won't persist between invocations on Vercel, so the
     dashboard shows the scheduled-items projection; the baseline stays a feature of the
     scheduled GitHub Actions run.)
   - Optional: `FORECAST_FLOOR`, `FOLIO_OPERATIONAL_ACCOUNT`, `FX_RATES`,
     `EXPECTED_INFLOWS_FILE`, `FORECAST_BASELINE=off`.
3. **Deploy**, open the URL, enter the `DASHBOARD_TOKEN`.

## Notes & limits

- **No persistent history on Vercel** → the run-rate baseline is effectively off there.
  The authoritative alerting path remains the scheduled GitHub Actions run (which caches
  state and history). The dashboard is a *view*, not the alerting engine.
- The function calls Folio live on each request; keep it behind the token and consider a
  short CDN cache only if needed (currently `no-store`).
- Read-only: the dashboard never triggers payments or alerts.

---

**Prev:** [← 07 · Roadmap](07-roadmap.md) · **Up:** [README](../README.md)
