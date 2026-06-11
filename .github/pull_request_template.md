<!--
Keep PRs small and focused. See CONTRIBUTING.md.
-->

## What & why

<!-- What does this change do, and why? Link any roadmap milestone or issue. -->

## Type

- [ ] Docs / spec
- [ ] Feature
- [ ] Fix
- [ ] Chore / tooling

## Checklist

- [ ] Scope is focused and the description explains the change.
- [ ] Docs updated where relevant (`docs/`, README doc map, cross-links resolve).
- [ ] If code: tests added/updated, tied to the [acceptance criteria](../docs/07-roadmap.md#2-acceptance-criteria).

## Security checklist

> Required for anything touching data handling, auth, logging, secrets, or external
> calls. See [`docs/06-security.md`](../docs/06-security.md).

- [ ] **No secrets** in the diff or history (gitleaks pre-commit + CI are green).
- [ ] Secrets read from env / secret store only — none added to `config` or committed files.
- [ ] Stays **read-only** against money movement (no `POST /payments`, `DELETE`, `PATCH /events`).
- [ ] Logs/errors redact tokens, webhook URLs, and account numbers.
- [ ] TLS + cert verification preserved for all external calls.
- [ ] N/A — this change doesn't touch any of the above.
