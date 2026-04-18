# Workflow Overview

## Branching
- Start new work from `main` using `feat/*`, `fix/*`, or `chore/*` prefixes.

## Pull Requests
- Keep PRs focused, reference related issues or ADRs, and request at least one reviewer.
- Merges require approved review and green CI checks.

<!-- ci-cd:start -->
## Checks

- `.github/workflows/ci.yml` is the pull request merge gate.
- Pull requests stay mergeable only when workflow validation,
  docs sync, backend, frontend, and security checks pass.
- `.github/workflows/deploy.yml` runs after merges to `main`
  and verifies the deployed API, worker, and optional frontend
  endpoints.
- `python scripts/ci/sync_docs.py` keeps the short generated
  CI/CD summaries aligned with the current repo shape.
<!-- ci-cd:end -->

## Pull Request Validation

`Pull Request Validation` is the merge gate. It validates workflow syntax with `actionlint`, checks generated CI/CD docs with `python scripts/ci/sync_docs.py --check`, runs backend linting, typing, tests, and startup smoke verification against sqlite, then runs frontend linting, typing, tests, and production build verification. Security checks stay in the same workflow so the PR fails in one place when dependency review, `npm audit`, `pip-audit`, `gitleaks`, or optional GitHub secret-scanning review detect a real problem.

The PR workflow does not call live Render, Vercel, or Supabase services. That keeps the merge gate deterministic enough for an AI-driven workflow where CI should validate the branch itself rather than transient platform state.

## Merge-to-main Deployment Verification

`Deployment Verification` runs after merges to `main` and on manual dispatch. The workflow waits for the normal Git-triggered deploy window, then checks:

- `DEPLOY_HEALTHCHECK_URL` for API readiness (`status=ok` and `database=ok`)
- `DEPLOY_WORKER_HEALTHCHECK_URL` for worker readiness (`status=ok` and classifier mode enabled)
- `DEPLOY_FRONTEND_URL` if you want the workflow to verify the hosted frontend responds with HTML

These checks confirm the deployed services are healthy without turning PR CI into a hosted-environment dependency.

## Required GitHub Settings

Configure these repository variables if the defaults do not match your hosted URLs or timing:

- `DEPLOY_HEALTHCHECK_URL`
- `DEPLOY_WORKER_HEALTHCHECK_URL`
- `DEPLOY_FRONTEND_URL` (optional)
- `DEPLOY_INITIAL_WAIT_SECONDS` (optional)
- `DEPLOY_TIMEOUT_SECONDS` (optional)
- `DEPLOY_POLL_INTERVAL_SECONDS` (optional)

Optional repository secret:

- `SECRET_SCAN_REVIEW_GITHUB_TOKEN` to enable GitHub secret-scanning review in PR CI when GitHub Advanced Security is available

Recommended branch protection on `main` is to require the PR validation workflow checks before merge.
If your repository previously required checks from the old `CI` workflow name or push-based runs, update those GitHub branch protection rules to the current pull-request validation checks so merges do not stall on obsolete statuses.

## Local Commands That Mirror CI

From the repository root:

```bash
python scripts/ci/sync_docs.py --check
python scripts/ci/verify_backend.py

cd services/api && python -m ruff check . && python -m mypy app && python -m pytest -q
cd apps/web && npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

For deployment verification logic only, you can also run:

```bash
python scripts/ci/verify_deploy.py --help
```
