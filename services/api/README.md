# StyleUs API Service

The API owns wardrobe persistence, private Supabase Storage upload finalization, and AI enrichment. It remains the business-logic boundary for the app in both local development and the planned production architecture.

## Stack

- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- PyJWT with Supabase JWKS verification
- Pillow / NumPy / scikit-learn
- `open-clip-torch` with optional ONNX inference
- Postgres-backed AI worker

## Service structure

- `app/main.py` - app creation, middleware, CORS, startup tasks
- `app/worker.py` - standalone AI worker entrypoint
- `app/api/routers` - health, version, item, and upload routes
- `app/services/ai_jobs.py` - durable AI job queue helpers and claim/retry logic
- `app/services/items.py` - wardrobe CRUD and response shaping
- `app/services/uploads.py` - signed-upload creation, private variant persistence, and upload finalization
- `app/utils/storage.py` - Supabase Storage REST adapter for signed reads, signed uploads, and object operations
- `app/ai` - CLIP heads, color extraction, segmentation, shared pipeline, and item enrichment logic
- `app/models` - SQLAlchemy models
- `app/seed` - deterministic seed dataset and runner

## Environment model

The backend explicitly supports:

- `APP_ENV=local`
- `APP_ENV=staging`
- `APP_ENV=production`

Local development reads from `services/api/.env`.

Staging and production should read from Render-managed environment variables. The backend remains Python/FastAPI in all environments; only the hosting and connected services change later.

### Database hosting

The backend data layer remains unchanged:

- SQLAlchemy is still the runtime ORM layer.
- Alembic is still the schema source of truth.
- `DATABASE_URL` is still the only database connection input.

What changes is where Postgres is hosted:

- local development defaults to Docker Postgres
- staging and production can point `DATABASE_URL` at Supabase Postgres

The settings layer normalizes `postgres://` and `postgresql://` URLs to the `postgresql+psycopg://` SQLAlchemy dialect automatically, so Supabase-provided connection strings can be pasted directly.

Hosted connection guidance for this phase:

- use a direct Supabase connection when possible
- Supavisor session pooling is also acceptable
- keep `sslmode=require` on hosted connections
- do not use transaction-pool mode for the API or Alembic in this phase

### Authentication

The backend now expects Supabase Auth bearer tokens in hosted environments.

- the frontend signs in with Supabase
- the frontend sends `Authorization: Bearer <token>` to the API
- FastAPI validates asymmetric Supabase tokens against the project JWKS endpoint
- legacy shared-secret tokens can fall back to `GET /auth/v1/user` when `SUPABASE_PUBLISHABLE_KEY` (or legacy `SUPABASE_ANON_KEY`) is set
- the token `sub` becomes the application user ID
- the API keeps business authorization and user-scoped queries in Python

Local development still supports an explicit bypass:

- `LOCAL_AUTH_BYPASS=true` allows the old single local user flow
- this bypass is only valid when `APP_ENV=local`
- the configured local identity (`LOCAL_AUTH_USER_ID`, `LOCAL_AUTH_EMAIL`) is also local-only and is reused by the seed commands
- `staging` and `production` must use real bearer tokens

### Startup safety

Startup-only convenience behavior is now config-gated:

- `RUN_MIGRATIONS_ON_START`
- `RUN_SEED_ON_START`

Default behavior:

- `local` -> migrations and seed are enabled by default
- `staging` / `production` -> both are disabled by default

This means local `make run` and `./dev.sh` remain convenient, while hosted environments do not mutate schema or seed data unless explicitly configured to do so.

`RUN_SEED_ON_START` replaces the older `SEED_ON_START` name. The legacy name is still accepted for compatibility, but the new flag is the canonical one.

## Current runtime flow

### Upload

1. `POST /items/presign`
2. A placeholder item is created in Postgres.
3. The client uploads the source image directly to a private Supabase Storage object using the signed upload target.
4. `POST /items/{item_id}/complete-upload`
5. The API downloads the private source object, generates `orig.jpg`, `medium.jpg`, `thumb.jpg`, stores private object paths plus metadata, and enqueues an `ai_jobs` row.
6. The worker polls `ai_jobs`, claims work with `SELECT ... FOR UPDATE SKIP LOCKED`, and writes predictions back to the item.

### AI enrichment

The worker-driven enrichment flow now looks like this:

- `POST /items/{item_id}/complete-upload` inserts or reuses a durable `ai_jobs` row with `pending` status.
- `app/worker.py` preloads the predictor once at startup, continuously polls the queue, and safely claims one row at a time.
- `app/ai/tasks.py` still owns the shared enrichment logic and writes back colors, category, subcategory, materials, style tags, top tags, and confidence when thresholds are met.
- The worker prefers the normalized `medium.jpg` variant for inference when it exists, which avoids downloading oversized originals for every job.
- Timing logs now report job claim latency, image fetch duration, preprocessing, inference, DB write, and total job duration.
- Job rows track `pending`, `running`, `completed`, and `failed` plus `attempts`, timestamps, and the latest error message.
- Running jobs that become stale are claimable again after `AI_JOB_STALE_AFTER_SECONDS`, which makes the worker restart-safe.
- Failed attempts are requeued until `AI_JOB_MAX_ATTEMPTS` is reached, then the job is marked `failed`.
- If a job takes longer than usual, check worker logs for `worker.warmup_started`, `worker.job_claimed`, `ai.tasks.image_fetch_started`, `ai.tasks.image_fetched`, and `ai.pipeline.timings` to see whether the delay is startup warmup, storage fetch, or inference.

### AI preview

`GET /items/{id}/ai-preview` returns a preview payload based on:

- persisted AI fields already stored on the item, plus
- the current queue state for the item's AI job.

If the worker has not finished yet, the preview returns `pending: true` and job metadata so the UI can keep polling without running inference in the API process.

## Routes

- `GET /health`
- `GET /version`
- `GET /items`
- `GET /items/{item_id}`
- `GET /items/{item_id}/ai-preview`
- `PATCH /items/{item_id}`
- `DELETE /items/{item_id}`
- `POST /items/presign`
- `PUT /items/uploads/{item_id}` legacy route that now returns `410 Gone`
- `POST /items/{item_id}/complete-upload`

## Environment variables

Copy `.env.example` to `.env` before running locally.

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `local`, `staging`, `production` | required |
| `APP_VERSION` | value returned by `/health` and `/version` | `0.1.0` |
| `DATABASE_URL` | SQLAlchemy/Postgres connection string; local Docker or Supabase-hosted | required |
| `SUPABASE_URL` | Supabase project URL used for auth verification and Storage API calls | required in hosted envs; optional for local boot |
| `SUPABASE_SERVICE_ROLE_KEY` | private backend key used for Supabase Storage operations | required in hosted envs and for local live uploads |
| `SUPABASE_STORAGE_BUCKET` | private bucket name for uploaded wardrobe media | required in hosted envs and for local live uploads |
| `SUPABASE_HTTP_TIMEOUT_SECONDS` | outbound timeout for Supabase Storage requests made by the API and worker | `15` |
| `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_ANON_KEY` | optional public key used only for legacy shared-secret token verification | _(unset)_ |
| `SUPABASE_JWT_AUDIENCE` | expected access-token audience | `authenticated` |
| `LOCAL_AUTH_BYPASS` | allow the local-only guest workflow without bearer tokens | `true` in local, otherwise `false` |
| `LOCAL_AUTH_USER_ID` / `LOCAL_AUTH_EMAIL` | explicit local bypass identity | local developer defaults |
| `CORS_ORIGINS` | comma-separated allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `MEDIA_MAX_UPLOAD_SIZE` | upload ceiling in bytes | `15728640` |
| `SUPABASE_SIGNED_URL_TTL_SECONDS` | signed read URL lifetime returned in item payloads | `3600` |
| `MEDIA_ROOT` | local scratch/cache directory still used by image/AI helpers | `./media` |
| `RUN_MIGRATIONS_ON_START` | run Alembic migrations during app startup | `true` in local, otherwise `false` |
| `RUN_SEED_ON_START` | apply deterministic seed data during app startup | `true` in local, otherwise `false` |
| `AI_ENABLE_CLASSIFIER` | enable background classification | `true` |
| `AI_DEVICE` | model device, usually `cpu` locally | `cpu` |
| `AI_CONFIDENCE_THRESHOLD` | write threshold for category/material/style updates | `0.6` |
| `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD` | write threshold for subcategory updates | `0.5` |
| `AI_COLOR_USE_MASK` | enable foreground masking before color clustering | `true` |
| `AI_COLOR_MASK_METHOD` | `grabcut` or `heuristic` | `grabcut` |
| `AI_COLOR_MIN_FOREGROUND_PIXELS` | minimum masked pixel count before unmasked fallback | `3000` |
| `AI_COLOR_TOPK` | number of colors retained from clustering | `2` |
| `AI_ONNX` / `AI_ONNX_MODEL_PATH` | optional ONNX inference path | `false` / unset |
| `AI_JOB_MAX_ATTEMPTS` | retry budget before a job is marked `failed` | `3` |
| `AI_JOB_POLL_INTERVAL_SECONDS` | worker sleep interval when no jobs are claimable | `0.5` |
| `AI_JOB_STALE_AFTER_SECONDS` | age after which a `running` job can be reclaimed | `300` |
| `SEED_LIMIT` / `SEED_KEY` | deterministic seed controls | `25` / `local-seed-v1` |

## Supabase Storage setup

The API now assumes a private Supabase Storage bucket.

Minimum dashboard configuration:

1. Create the bucket named by `SUPABASE_STORAGE_BUCKET`.
2. Keep the bucket private.
3. Set the bucket file size limit to match `MEDIA_MAX_UPLOAD_SIZE`.
4. Restrict allowed MIME types to `image/jpeg`, `image/png`, and `image/webp`.
5. Store `SUPABASE_SERVICE_ROLE_KEY` only on the backend.

Security model:

- the browser never receives the service-role key
- the API issues short-lived signed upload targets
- item payloads expose only signed read URLs, not permanent public URLs
- AI/seed/server-side flows use direct authenticated Storage access from the backend

## Local development

```bash
cd services/api
cp .env.example .env
make setup
make db-up
make upgrade
cd ../..
./dev.sh
```

Default API URL: `http://127.0.0.1:8000`

`./dev.sh` now starts the API, the AI worker, and the frontend together. If you prefer separate processes, `make run` and `make worker` still work independently.

The copied example file includes placeholder Supabase Storage values. Replace them before exercising the live upload path.

Useful commands:

- `make seed` - apply the deterministic seed dataset
- `make reset-seed` - remove seeded items and their stored media objects
- `make worker` - start the AI worker loop
- `make lint`
- `make typecheck`
- `make test`

`make seed` and `make reset-seed` are local-development commands. They now refuse to run unless `APP_ENV=local`, because the seed dataset attaches to the configured local auth identity.

To test real auth locally:

1. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` in `services/api/.env`
2. Set `LOCAL_AUTH_BYPASS=false`
3. If your Supabase project still uses legacy shared-secret JWT signing, also set `SUPABASE_PUBLISHABLE_KEY`
4. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in `apps/web/.env.local`
5. Create the private Storage bucket in Supabase and align its size/MIME rules with `MEDIA_MAX_UPLOAD_SIZE`
6. Sign in from the web app

## Running against Supabase Postgres

The backend does not need a different code path for Supabase. Point `DATABASE_URL` at a Supabase Postgres connection string and keep using the existing commands.

Recommended migration flow against Supabase:

```bash
cd services/api
export APP_ENV=staging
export DATABASE_URL='postgresql://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require'
export SUPABASE_URL='https://<project-ref>.supabase.co'
export SUPABASE_SERVICE_ROLE_KEY='<service-role-key>'
export SUPABASE_STORAGE_BUCKET='wardrobe-images'
export RUN_MIGRATIONS_ON_START=false
export RUN_SEED_ON_START=false
make upgrade
make run
```

Notes:

- `make upgrade` remains the canonical schema migration path.
- The app will normalize the Supabase URL to the correct SQLAlchemy psycopg driver automatically.
- Use the same `DATABASE_URL` for Alembic and the API process.
- Local Docker Postgres remains the default for `./dev.sh` and `make db-up`.

## Platform boundary

### Local today

- API runs on the host.
- Postgres runs in Docker.
- Uploaded media lives in a private Supabase Storage bucket.
- Auth can use either:
  - explicit local bypass, or
  - real Supabase bearer tokens when configured locally

### Target hosted shape

- Render web service -> FastAPI API
- Render worker -> AI worker runtime using the same Postgres queue
- Supabase Postgres -> supported hosted database target in this phase
- Supabase Auth -> implemented for bearer-token validation in this phase
- Supabase Storage -> implemented in this phase for private uploads and signed reads

The API remains the only component that should own:

- business CRUD
- upload finalization
- AI prediction persistence
- user-scoped authorization rules

The frontend should only know public API and public auth configuration. Database credentials, storage credentials, and server-side secrets remain backend-only.

## Deployment notes for later phases

This repository is now documented for the target platform split, but the following are still future work:

- staging and production rollout

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
