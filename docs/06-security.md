# 06 · Security & privacy

**Part of the [Liquidity Forecaster spec](../README.md).**

This tool handles **live banking credentials and financial data**. Every requirement
here is normative for any implementation — "should" denotes a strong default, "must"
is non-negotiable.

---

## 1. Threat model & assets

**What we protect (assets):**

| Asset | Sensitivity | Where it lives |
|---|---|---|
| Folio API key / OAuth2 refresh token | **Critical** — read access to all company banking data | Secret store / env |
| Slack webhook URL or bot token | High — anyone with it can post as the app | Secret store / env |
| SMTP / Gmail credentials | High | Secret store / env |
| Account balances & history | High — financial data | Local store |
| Creditor names / account numbers | High — **personal data (GDPR)** | Local store, alerts |

**Primary threats:** secret leakage (commits, logs, error messages), unauthorized read
of the local store, a compromised dependency exfiltrating data, and over-broad API
access enabling money movement. **Out of scope for v1:** multi-tenant isolation (single
company), and defending a fully compromised host.

**Posture:** the forecaster is **read-only against money movement** and treats all
secrets as externally injected. It is a small, single-tenant internal tool — the design
favours *not holding* sensitive data over protecting large stores of it.

---

## 2. Secrets management
- **MUST NOT** commit any secret. The [`.gitignore`](../.gitignore) blocks `.env*`,
  key files, and local databases; this is a backstop, not the primary control.
- Secrets are injected via **environment variables or a secret manager** (e.g. cloud
  secret store, CI secret, or a `.env` that is git-ignored and file-permission-restricted).
  Config tables hold only *non-secret* settings (floor, horizon, `#finance`); credential
  *values* never appear in `config`.
- **MUST NOT** log secret values, full `Authorization` headers, webhook URLs, or tokens.
- Run a **pre-commit secret scanner** (e.g. gitleaks) and a CI secret-scan to catch
  accidental commits before they land.

## 3. Least privilege & read-only posture
- The application **MUST NOT** call money-moving endpoints: `POST /payments`,
  `DELETE /payments/{id}`, `PATCH /events`, attachment/complete mutations. It only
  issues the read calls listed in [Data & accounts §2](02-data-and-accounts.md).
- Where Folio supports scoped keys, provision a **read-only** key. If only a full-access
  personal key is available, compensate with the code-level allowlist above and review.
- The runtime identity/service account has **least privilege** on its host (no broad
  cloud roles, no write access it doesn't need).

## 4. Transport & runtime
- **All** Folio/Slack/SMTP calls over **TLS**; certificate verification **on** (never
  disable it). No secrets or financial data over plaintext channels.
- Pin a sane HTTP timeout and retry budget; fail closed (no alert lost) on errors
  (see [Alerting §4.4/§4.5](04-alerting.md)).

## 5. Data at rest, minimization & retention
- The local store (SQLite/JSON) holds financial + personal data → restrict to
  **owner-only file permissions** (`0600`) and consider **encryption at rest**
  (encrypted volume or app-level encryption) on shared/cloud hosts.
- **Data minimization:** store only what the forecast needs. Don't persist full
  transaction detail, attachments, or merchant PII beyond what drives the projection.
- **Retention:** historical daily balances are kept for the lookback window plus a
  modest margin; prune older rows. Alert history is kept only as long as useful for the
  state-change rule. Define concrete retention periods before go-live.

## 6. Logging, redaction & error handling
- **Redact in logs:** mask account numbers (e.g. last 4 only), never log tokens,
  webhook URLs, or full API responses. Treat balances/creditor names as sensitive.
- **Error handling:** exceptions and stack traces **MUST NOT** leak secrets or full
  payloads into logs, Slack, or email. User-facing alert text contains only the
  forecast summary, not raw API data or internal diagnostics.

## 7. Dependencies & supply chain
- **Pin** dependencies (lockfile) and keep the surface small.
- Run **`pip-audit`/`npm audit`** (or equivalent) in CI; enable **Dependabot** (or
  similar) for security updates.
- Review new transitive dependencies before adding; prefer well-maintained libraries
  for HTTP, decimal math, and Slack/email.

## 8. Input & response validation
- **Schema-validate** Folio responses against the documented types before use; reject
  / flag malformed payloads rather than trusting them.
- Parse all monetary strings into **fixed-point decimal** (never float); validate
  against the documented patterns (`^\d+\.\d+$`, 2dp for `TransactionAmount`).
- Treat any externally controlled string (creditor names, messages) as untrusted when
  composing Slack/email — avoid markup/formatting injection.

## 9. Auth lifecycle
- Support **key rotation** without code changes (read from secret store each run).
- If the **OAuth2** path is chosen (vs personal API key — see
  [Roadmap open questions](07-roadmap.md#3-open-questions)), store the **refresh token**
  as a critical secret, handle token refresh server-side, and support revocation via
  Folio's `POST /integration/disable`.

## 10. Privacy / GDPR (EU / Norway)
- Creditor names and account numbers are **personal data**; processing needs a lawful
  basis (legitimate interest / contract for running the business's finances).
- **Data residency:** prefer EU/EEA hosting and EU-based sub-processors (Slack, email).
- Apply **data minimization** and **retention limits** (§5); support deletion on request.
- Document processing in the company's records where required; this internal tool should
  not expand the data footprint beyond what Folio already holds.

---

## Security checklist (pre-go-live)
- [ ] No secret in git history; pre-commit + CI secret scan active.
- [ ] Secrets injected from env/secret store; `config` holds no credential values.
- [ ] Read-only API key (or code allowlist) — no money-moving calls reachable.
- [ ] TLS enforced with cert verification everywhere.
- [ ] Local store permissions `0600` (+ encryption on shared hosts); retention defined.
- [ ] Logs redact account numbers; never log tokens/full payloads.
- [ ] Dependencies pinned; `audit` clean in CI; Dependabot on.
- [ ] Folio responses schema-validated; money parsed as decimal.
- [ ] Key rotation works without redeploy; OAuth refresh token stored as secret (if used).
- [ ] GDPR: lawful basis recorded, EU residency, retention + deletion path.

---

**Prev:** [← 05 · Architecture](05-architecture.md) · **Next:** [07 · Roadmap →](07-roadmap.md)
