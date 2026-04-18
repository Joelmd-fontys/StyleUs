# Compatibility Inventory

This document freezes the repo-facing boundaries that Task 1 characterization tests and later structural refactors must preserve.

## Public REST interfaces

- `GET /items` remains the dashboard and wardrobe listing endpoint, including support for `category`, `q`, `limit`, `offset`, and `createdSince` query parameters.
- `POST /items/presign` remains the upload initiation endpoint and returns `uploadUrl`, `itemId`, and, for direct Supabase uploads, `objectKey`, `uploadToken`, and `bucket`.
- `POST /items/{item_id}/complete-upload` remains the upload finalization endpoint and accepts the current JSON body shape (`fileName`, optional `objectKey`, optional `imageUrl`).
- `GET /items/{item_id}/ai-preview` remains the review polling endpoint and returns persisted prediction fields plus `pending` and optional `job` state.
- `PATCH /items/{item_id}` remains the review-save endpoint and continues to accept `reviewFeedback.predictedCategory`, `reviewFeedback.predictionConfidence`, and `reviewFeedback.acceptedDirectly`.
- `PUT /items/uploads/{item_id}` remains intentionally unsupported with explicit `410 Gone` behavior.

## Runtime entrypoints and deploy surfaces

- Local orchestration remains rooted at `./dev.sh`, which runs migrations, starts `app.main:app` on port `8000`, starts `app.worker_service:app` on port `8001`, and starts the Vite app on port `5173`.
- Repo convenience entrypoints remain `make test`, `make lint`, and `make typecheck`, delegating into `services/api` and `apps/web`.
- Hosted backend topology remains the Render services named `styleus-api` and `styleus-ai-worker` from `render.yaml`.
- Hosted frontend deployment remains the Vercel app under `apps/web`, with `apps/web/vercel.json` preserving the `npm run build` build command, `dist` output, and SPA rewrite to `/index.html`.

## Environment and boundary toggles

- `APP_ENV=local` remains the only environment where `LOCAL_AUTH_BYPASS` is valid.
- `RUN_MIGRATIONS_ON_START` remains a backend startup toggle accepted by both local and hosted runtime paths.
- `RUN_SEED_ON_START` remains the primary seed toggle, while `SEED_ON_START` remains a legacy alias.
- `VITE_USE_LIVE_API_ITEMS` and `VITE_USE_LIVE_API_UPLOAD` remain the local web toggles that switch between MSW-backed mock flows and the live API/upload path.

## Upload, review, and dashboard semantics

- The visible upload flow remains: choose image in `#upload-panel` -> presign -> upload -> complete-upload -> navigate to `/upload/review/:id`.
- The upload panel continues to reject non-image files inline with `Only image files are supported.` and keeps the user on `/wardrobe`.
- The review screen continues to poll `GET /items/{id}/ai-preview` while predictions are pending and keeps the page interactive once analysis settles.
- The dashboard recent-items rail continues to fetch up to four items and uses `createdSince` after a clear action so cleared items stay hidden until refresh/newer uploads.
