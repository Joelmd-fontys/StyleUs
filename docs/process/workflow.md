# Workflow Overview

## Branching
- Start new work from `main` using `feat/*`, `fix/*`, or `chore/*` prefixes.

## Pull Requests
- Keep PRs focused, reference related issues or ADRs, and request at least one reviewer.
- Merges require approved review and green CI checks.

<!-- ci-cd:start -->
## Checks

- `.github/workflows/ci.yml` runs on every pull request and push.
- Pull requests stay mergeable only when backend, frontend, security, build, and documentation checks pass.
- `python scripts/ci/sync_docs.py` keeps the managed docs sections aligned with the repository shape and deployment workflow.
- `.github/workflows/deploy.yml` runs after merges to `main` and verifies the deployed API health endpoint.
<!-- ci-cd:end -->
