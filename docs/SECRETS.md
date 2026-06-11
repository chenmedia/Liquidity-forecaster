# Handling secrets

How to supply credentials to the Liquidity Forecaster **without ever committing or
exposing them**. This complements the policy in [06-security.md](06-security.md).

> **Golden rule:** secrets live in the environment or a secret manager — never in
> the repo, never in chat/tickets/commit messages, never in logs.

---

## Required secrets

| Variable | Purpose | Where to get it |
|---|---|---|
| `FOLIO_API_KEY` | Read-only Folio banking access | [app.folio.no/til/api-tilgang](https://app.folio.no/til/api-tilgang) |
| `SLACK_WEBHOOK_URL` *or* `SLACK_BOT_TOKEN` | Post alerts to `#finance` | Slack app / incoming-webhook config |
| `SMTP_*` | Email fallback when Slack fails | Your mail provider |

Non-secret settings (floor, horizon, channel name) live in app config, **not** here.

---

## Local development

```bash
cp .env.example .env        # .env is git-ignored
# edit .env, paste real values
```

`.env` is matched by [`.gitignore`](../.gitignore) and cannot be committed. Restrict
its permissions:

```bash
chmod 600 .env
```

Only `.env.example` (placeholders) is tracked in git.

## Production / CI

Do **not** ship a `.env`. Inject variables from the platform's secret store:

- **CI:** repository/organization **secrets** (e.g. GitHub Actions secrets).
- **Cloud:** a secret manager (AWS Secrets Manager, GCP Secret Manager, Azure Key
  Vault, etc.), read at startup.
- **Containers:** mounted secrets / orchestrator secrets — not baked into images.

### Scheduled run on GitHub Actions

The [`forecast.yml`](../.github/workflows/forecast.yml) workflow runs the forecaster
daily. It **skips cleanly** until `FOLIO_API_KEY` is set, so it's safe to merge first.
To enable it, add these under **Settings → Secrets and variables → Actions**:

| As a **secret** | Purpose |
|---|---|
| `FOLIO_API_KEY` | Folio read access (required to enable the run) |
| `SLACK_WEBHOOK_URL` | Post alerts to `#finance` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `ALERT_EMAIL_FROM` | Email fallback |

| As a **variable** (non-secret) | Purpose |
|---|---|
| `SLACK_CHANNEL` (default `#finance`), `ALERT_EMAIL_TO` | Routing |
| `FORECAST_FLOOR`, `FORECAST_HORIZON_DAYS` | Tune thresholds without code changes |
| `FOLIO_OPERATIONAL_ACCOUNT` | Which Operational account to forecast (if you run several) |

Manual runs (**Actions → Liquidity forecast → Run workflow**) default to **dry-run**.

---

## Automated secret scanning

The repo is wired to catch secrets before they're committed and again in CI:

- **Local (pre-commit):** [gitleaks](https://github.com/gitleaks/gitleaks) runs on every
  `git commit`. Enable it once per clone:
  ```bash
  pip install pre-commit     # or: brew install pre-commit
  pre-commit install
  ```
  Config: [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) +
  [`.gitleaks.toml`](../.gitleaks.toml) (includes a custom rule for Folio `fk.` keys
  and an allowlist for `.env.example`).
- **CI (backstop):** [`.github/workflows/secret-scan.yml`](../.github/workflows/secret-scan.yml)
  runs gitleaks over the **full history** on every push and PR. Local hooks can be
  bypassed with `--no-verify`; CI cannot, so this is the real enforcement.

If a scan ever fires, **do not** `--no-verify` around it — rotate the exposed secret
(below) and remove it from the change.

## Rotation & incident response

Rotate immediately (treat the old value as compromised) if a secret is ever pasted
into chat, a ticket, an email, a screenshot, or committed by accident:

1. **Revoke** the exposed credential at its source
   (Folio: [api-tilgang](https://app.folio.no/til/api-tilgang); Slack: regenerate the
   webhook/token; mail: reset the SMTP password).
2. **Issue a new** credential.
3. **Update** the env var / secret-store entry — never paste the new value into chat.
4. If it was committed, also **purge git history** (e.g. `git filter-repo`) and
   force-rotate, since history persists on any clone/fork.

## What NOT to do
- ❌ Paste a key into chat, a PR description, or a commit message.
- ❌ Commit a real `.env`, `credentials.json`, or any token file.
- ❌ `print`/`log` a token, `Authorization` header, or webhook URL.
- ❌ Email or Slack a secret to a teammate — share via the secret manager.
