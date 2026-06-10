# Contributing

Thanks for working on the Liquidity Forecaster. This repo is currently a
**specification** (see [`docs/`](docs/)); application code will follow the milestones
in [`docs/07-roadmap.md`](docs/07-roadmap.md). These conventions keep development smooth
and — given this tool touches live banking data — safe.

## One-time setup

```bash
git clone <repo> && cd liquidity-forecaster
pip install pre-commit       # or: brew install pre-commit
pre-commit install           # enables the gitleaks secret-scan hook
cp .env.example .env          # then fill in real values (never commit .env)
```

See [`docs/SECRETS.md`](docs/SECRETS.md) for how to supply credentials safely.

## Branch & PR flow

1. Branch off `main`: `git switch -c <type>/<short-description>`
   (`feat/…`, `fix/…`, `docs/…`, `chore/…`).
2. Make focused commits with clear messages (imperative mood: "Add …", "Fix …").
3. Push and open a PR into `main`. Fill in the
   [PR template](.github/pull_request_template.md) — including the **security checklist**.
4. CI (secret scan) must be green. Keep PRs small and reviewable.
5. Squash-or-merge once approved and green.

## Documentation conventions

- The spec lives in numbered files under `docs/` (`01-…` to `07-…`) with a `README`
  index. Keep them cross-linked; when you add a section, update any references.
- Prefer editing the relevant `docs/NN-*.md` over growing one file. Update the
  [README doc map](README.md#documentation) if you add or rename a doc.

## Security gate (non-negotiable)

- **Never commit secrets.** The `.gitignore` + gitleaks (pre-commit and CI) are
  backstops, not permission to be careless. Don't `git commit --no-verify` around a
  secret-scan failure — rotate the secret instead (see
  [`docs/SECRETS.md`](docs/SECRETS.md)).
- Any change that touches data handling, auth, logging, or external calls must satisfy
  [`docs/06-security.md`](docs/06-security.md) and its pre-go-live checklist.
- The tool stays **read-only** against money movement — no calls to `POST /payments`,
  `DELETE /payments/{id}`, or `PATCH /events`.

## When code lands

Each implementation milestone should ship with tests tied to the
[acceptance criteria](docs/07-roadmap.md#2-acceptance-criteria) (the worked example in
[`docs/03-forecast.md`](docs/03-forecast.md#5-worked-example-v1-committed-scenario-baseline--0)
is the canonical fixture). Wire the test command into CI alongside the secret scan.
