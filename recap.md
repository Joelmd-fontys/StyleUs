# Repository Recap

## Current shape

<!-- current-shape:start -->
- `apps/web` contains the only frontend application and is deployed by Vercel.
- `services/api` contains the API, worker service, migrations,
  and seed pipeline, and is deployed by Render.
- `.github/workflows/ci.yml` validates workflow syntax, docs,
  code quality, tests, builds, and security for pull requests.
- `.github/workflows/deploy.yml` verifies the production
  backend health after merges to `main`, and can optionally
  verify the frontend URL too.
- `docs` contains only cross-cutting notes that are still
  relevant to operation, deployment, or delivery workflow.
<!-- current-shape:end -->

## Upload and prediction flow

1. The web app requests `POST /items/presign`.
2. The browser uploads directly to private Supabase Storage.
3. `POST /items/{item_id}/complete-upload` writes image variants and queues an `ai_jobs` row.
4. The worker service processes the queued job and stores predictions.
5. The review page polls `GET /items/{id}/ai-preview` until the result is ready.

## Cleanup decisions reflected in the repo

- removed tracked local media artifacts from `services/api/media`
- removed placeholder READMEs and historical planning docs that were not part of the active system
- removed the unused S3 helper path and its unused Python dependency
- aligned `.env.example` files with the active Supabase-based runtime
- simplified `.gitignore` so generated files stay ignored and tracked app files stay visible
- trimmed the main docs to current architecture, setup, and deployment boundaries

## Local run

Use `./dev.sh` from the repo root for the full stack, or run the web app and API separately from `apps/web` and `services/api`.

## Remaining manual work outside the repo

- hosted deployment rollout
- Supabase project configuration for auth and private storage
- repository variable and secret rollout for deployment verification and optional secret-scanning review

<!-- ci-cd:start -->
## CI/CD Pipeline

- PRs fail on backend or frontend validation errors,
  documentation drift, dependency review issues, high or
  critical audit findings, or detected secrets.
- The docs sync script owns the short generated CI/CD summaries
  in `README.md`, `docs/architecture/deployment.md`,
  `docs/config/environments.md`, `docs/process/workflow.md`,
  and `recap.md`.
- Production deploys stay platform-native: Vercel handles the
  web app, Render rebuilds the API and worker services, and
  GitHub Actions verifies the hosted health endpoints after
  merge.
<!-- ci-cd:end -->
