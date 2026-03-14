# StyleUs API Service

The API owns wardrobe persistence, upload finalization, signed media URLs, and the durable AI job queue. It is the single business-logic boundary for the web app.

## Key modules

- `app/main.py` - FastAPI app, middleware, and startup hooks
- `app/api/routers` - health, version, item, and upload routes
- `app/services/items.py` - wardrobe CRUD and response shaping
- `app/services/uploads.py` - signed uploads, image variants, and upload completion
- `app/services/ai_jobs.py` - queue claim, retry, and completion helpers
- `app/ai/worker.py` - reusable AI worker runtime used by the worker service and CLI
- `app/worker.py` - optional CLI entrypoint for one-off worker runs
- `app/worker_service.py` - minimal FastAPI worker service with `/health`
- `app/ai` - color extraction, segmentation, CLIP heads, and enrichment pipeline
- `app/seed` - deterministic local seed dataset

## Local development

```bash
cd services/api
cp .env.example .env
make setup
make db-up
make upgrade
make run
make worker-service
```

`make run` starts only the API. `make worker-service` starts the lightweight worker web service. From the repo root, `./dev.sh` starts the API, worker, frontend, database, and migrations together.

Useful commands:

- `make worker-service` - local worker web service on `http://127.0.0.1:8001/health`
- `make worker` - optional standalone worker loop for one-off debugging
- `make seed`
- `make reset-seed`
- `make lint`
- `make typecheck`
- `make test`

## Core routes

- `GET /health`
- `GET /version`
- `GET /items`
- `GET /items/{item_id}`
- `GET /items/{item_id}/ai-preview`
- `PATCH /items/{item_id}`
- `DELETE /items/{item_id}`
- `POST /items/presign`
- `POST /items/{item_id}/complete-upload`

The legacy `PUT /items/uploads/{item_id}` route remains as a `410 Gone` response so older clients fail explicitly.

## Upload and AI flow

1. `POST /items/presign` creates a placeholder item and returns a signed upload target.
2. The browser uploads the source image directly to private Supabase Storage.
3. `POST /items/{item_id}/complete-upload` validates the source object, writes `orig.jpg`, `medium.jpg`, and `thumb.jpg`, and enqueues an `ai_jobs` row.
4. The worker service launches the `app/ai/worker.py` loop in a background thread, and it polls the queue with `SELECT ... FOR UPDATE SKIP LOCKED`.
5. `GET /items/{item_id}/ai-preview` returns persisted predictions plus queue state so the UI can keep polling without re-running inference in the API.

## Environment variables

Copy `.env.example` to `.env` before running locally.

Required for hosted deployments:

- `APP_ENV` - set to `production` on Render
- `DATABASE_URL` - Supabase Postgres connection string; include `sslmode=require`
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - backend-only key for private Storage access
- `SUPABASE_STORAGE_BUCKET` - private bucket used for original and derived images
- `CORS_ORIGINS` - comma-separated Vercel origins allowed to call the API
- `AI_JOB_MAX_ATTEMPTS` - worker retry limit
- `AI_JOB_POLL_INTERVAL_SECONDS` - worker poll interval

Common optional settings:

- `APP_VERSION`
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_SIGNED_URL_TTL_SECONDS`
- `SUPABASE_HTTP_TIMEOUT_SECONDS`
- `AI_JOB_STALE_AFTER_SECONDS`
- `AI_ENABLE_CLASSIFIER`
- `AI_DEVICE`
- `AI_CONFIDENCE_THRESHOLD`
- `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`
- `AI_COLOR_USE_MASK`
- `AI_COLOR_MASK_METHOD`
- `AI_COLOR_MIN_FOREGROUND_PIXELS`
- `AI_COLOR_TOPK`
- `AI_ONNX`
- `AI_ONNX_MODEL_PATH`

Local-only settings:

- `LOCAL_AUTH_BYPASS`, `LOCAL_AUTH_USER_ID`, `LOCAL_AUTH_EMAIL`
- `RUN_MIGRATIONS_ON_START`, `RUN_SEED_ON_START`, `SEED_LIMIT`, `SEED_KEY`
- `MEDIA_ROOT`, `MEDIA_MAX_UPLOAD_SIZE`
- `SUPABASE_ANON_KEY` only for legacy shared-secret token verification

Rules:

- `LOCAL_AUTH_BYPASS` is valid only when `APP_ENV=local`.
- `RUN_MIGRATIONS_ON_START` and `RUN_SEED_ON_START` default to `true` only in `local`.
- `SEED_ON_START` is still accepted as a legacy alias for `RUN_SEED_ON_START`.
- Hosted environments should keep `RUN_MIGRATIONS_ON_START=false` and `RUN_SEED_ON_START=false`.

## Render deployment

The repository includes [render.yaml](../../render.yaml) for the hosted backend shape:

- `styleus-api` -> Render web service using `services/api/Dockerfile`
- `styleus-ai-worker` -> Render web service using the same Docker image with `dockerCommand: uvicorn app.worker_service:app --host 0.0.0.0 --port ${PORT}`

API service settings:

- Root Directory: `services/api`
- Runtime: `Docker`
- Health Check Path: `/health`
- Pre-Deploy Command: `python -m alembic upgrade head`
- Start Command: Docker default from `services/api/Dockerfile`

Deployment notes:

- The Docker image binds uvicorn to `${PORT:-8000}` so it runs cleanly on Render.
- The API uses the Dockerfile `CMD`; the worker overrides it with `dockerCommand`.
- `/health` on the API checks database connectivity, and `/health` on the worker checks worker liveness plus queue visibility.
- Use the same `DATABASE_URL` for Alembic, the API runtime, and the worker runtime.
- Local Docker Postgres remains the default for `./dev.sh` and `make db-up`.

## Platform boundary

### Local today

- API runs on the host.
- Postgres runs in Docker.
- Uploaded media lives in a private Supabase Storage bucket.
- Auth can use either:
  - explicit local bypass, or
  - real Supabase bearer tokens when configured locally

### Hosted shape

- Render web service -> FastAPI API
- Render web service -> minimal AI worker service
- Supabase Postgres -> supported hosted database target in this phase
- Supabase Auth -> implemented for bearer-token validation in this phase
- Supabase Storage -> implemented in this phase for private uploads and signed reads

The API remains the only component that should own:

- business CRUD
- upload finalization
- user-scoped authorization rules

The worker service owns:

- asynchronous AI job claiming
- retry and stale-job recovery
- AI prediction persistence

The frontend should only know public API and public auth configuration. Database credentials, storage credentials, and server-side secrets remain backend-only.

## Deployment notes

The checked-in blueprint and local scripts reflect the current two-service Render deployment shape. Add or rename environments by extending `render.yaml` and the corresponding Render/Vercel project settings.

## Docker and Postgres

- `docker-compose.yml` starts Postgres only.
- Normal development runs the API on the host, not in Docker.
- The database container is named `styleus-db`.
- Data is persisted in the `styleus-pgdata` Docker volume.

## Testing notes

- Backend tests run with pytest.
- The current test configuration expects a Postgres database reachable via `DATABASE_URL`; the default test setup points at `postgresql+psycopg://postgres:postgres@localhost:5432/postgres`.
- Supabase Storage interactions are mocked in unit tests.

See also:

- [../../docs/config/environments.md](../../docs/config/environments.md)
- [../../docs/architecture/deployment.md](../../docs/architecture/deployment.md)
