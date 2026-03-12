# Repository Recap

## Current shape

- `apps/web` contains the only frontend application.
- `services/api` contains the API, worker, migrations, and seed pipeline.
- `docs` contains only cross-cutting notes that are still relevant to operation or deployment.

## Upload and prediction flow

1. The web app requests `POST /items/presign`.
2. The browser uploads directly to private Supabase Storage.
3. `POST /items/{item_id}/complete-upload` writes image variants and queues an `ai_jobs` row.
4. The worker processes the queued job and stores predictions.
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
- CI hardening beyond the current placeholder workflow
