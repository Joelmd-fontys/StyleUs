# StyleUs API Service

The API owns wardrobe persistence, upload finalization, local media serving, and AI enrichment. It remains the business-logic boundary for the app in both local development and the planned production architecture.

## Stack

- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Pillow / NumPy / scikit-learn
- `open-clip-torch` with optional ONNX inference
- FastAPI `BackgroundTasks`

## Service structure

- `app/main.py` - app creation, middleware, CORS, media mount, startup tasks
- `app/api/routers` - health, version, item, and upload routes
- `app/services/items.py` - wardrobe CRUD and response shaping
- `app/services/uploads.py` - presign, local upload persistence, and upload finalization
- `app/ai` - CLIP heads, color extraction, segmentation, pipeline coordination, background task logic
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
3. The client uploads bytes either:
   - to `PUT /items/uploads/{item_id}` in local upload mode, or
   - directly to S3 in S3 mode.
4. `POST /items/{item_id}/complete-upload`
5. The API generates `orig.jpg`, `medium.jpg`, `thumb.jpg`, stores metadata, and schedules AI classification.

### AI enrichment

The background task in `app/ai/tasks.py`:

- loads the finalized image from local media or S3;
- runs the shared pipeline in `app/ai/pipeline.py`;
- writes back colors, category, subcategory, materials, style tags, top tags, and confidence when thresholds are met;
- avoids overwriting user-supplied data unless fields are still empty or placeholder-like.

### AI preview

`GET /items/{id}/ai-preview` returns a preview payload based on:

- persisted AI fields already stored on the item, plus
- a fresh non-persisted pipeline pass when the source image is available.

That preview endpoint is still designed for the upload review UI. It is not yet backed by a separate job or prediction model.

## Routes

- `GET /health`
- `GET /version`
- `GET /items`
- `GET /items/{item_id}`
- `GET /items/{item_id}/ai-preview`
- `PATCH /items/{item_id}`
- `DELETE /items/{item_id}`
- `POST /items/presign`
- `PUT /items/uploads/{item_id}` in local upload mode
- `POST /items/{item_id}/complete-upload`

## Environment variables

Copy `.env.example` to `.env` before running locally.

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `local`, `staging`, `production` | `local` |
| `APP_VERSION` | value returned by `/health` and `/version` | `0.1.0` |
| `API_KEY` | temporary secure-env guard until real auth arrives | _(unset)_ |
| `DATABASE_URL` | SQLAlchemy/Postgres connection string; local Docker or Supabase-hosted | required |
| `CORS_ORIGINS` | comma-separated allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `UPLOAD_MODE` | `local` or `s3`; auto-derived if omitted | auto |
| `MEDIA_ROOT` | local media directory | `./media` |
| `MEDIA_URL_PATH` | static mount path for local media | `/media` |
| `MEDIA_MAX_UPLOAD_SIZE` | upload ceiling in bytes | `15728640` |
| `RUN_MIGRATIONS_ON_START` | run Alembic migrations during app startup | `true` in local, otherwise `false` |
| `RUN_SEED_ON_START` | apply deterministic seed data during app startup | `true` in local, otherwise `false` |
| `AWS_REGION` / `S3_BUCKET_NAME` | required only for S3 mode | _(unset)_ |
| `AI_ENABLE_CLASSIFIER` | enable background classification | `true` |
| `AI_DEVICE` | model device, usually `cpu` locally | `cpu` |
| `AI_CONFIDENCE_THRESHOLD` | write threshold for category/material/style updates | `0.6` |
| `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD` | write threshold for subcategory updates | `0.5` |
| `AI_COLOR_USE_MASK` | enable foreground masking before color clustering | `true` |
| `AI_COLOR_MASK_METHOD` | `grabcut` or `heuristic` | `grabcut` |
| `AI_COLOR_MIN_FOREGROUND_PIXELS` | minimum masked pixel count before unmasked fallback | `3000` |
| `AI_COLOR_TOPK` | number of colors retained from clustering | `2` |
| `AI_ONNX` / `AI_ONNX_MODEL_PATH` | optional ONNX inference path | `false` / unset |
| `SEED_LIMIT` / `SEED_KEY` | deterministic seed controls | `25` / `local-seed-v1` |

## Local development

```bash
cd services/api
cp .env.example .env
make setup
make db-up
make upgrade
make run
```

Default API URL: `http://127.0.0.1:8000`

Useful commands:

- `make seed` - apply the deterministic seed dataset
- `make reset-seed` - remove seeded items and their media
- `make lint`
- `make typecheck`
- `make test`

## Running against Supabase Postgres

The backend does not need a different code path for Supabase. Point `DATABASE_URL` at a Supabase Postgres connection string and keep using the existing commands.

Recommended migration flow against Supabase:

```bash
cd services/api
export APP_ENV=staging
export DATABASE_URL='postgresql://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require'
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
- Media is local disk by default unless S3 mode is configured.
- Auth is still a stub user model.

### Target hosted shape

- Render web service -> FastAPI API
- Render worker -> future background worker, not implemented yet
- Supabase Postgres -> supported hosted database target in this phase
- Supabase Auth and Supabase Storage -> later phases

The API remains the only component that should own:

- business CRUD
- upload finalization
- AI prediction persistence
- user-scoped authorization rules

The frontend should only know public API and public auth configuration. Database credentials, storage credentials, and server-side secrets remain backend-only.

## Deployment notes for later phases

This repository is now documented for the target platform split, but the following are still future work:

- Supabase Auth integration
- Supabase Storage migration
- separate background worker runtime
- staging and production rollout

## Docker and Postgres

- `docker-compose.yml` starts Postgres only.
- Normal development runs the API on the host, not in Docker.
- The database container is named `styleus-db`.
- Data is persisted in the `styleus-pgdata` Docker volume.

## Testing notes

- Backend tests run with pytest.
- The current test configuration expects a Postgres database reachable via `DATABASE_URL`; the default test setup points at `postgresql+psycopg://postgres:postgres@localhost:5432/postgres`.
- AWS interactions are mocked in unit tests.

See also:

- [../../docs/config/environments.md](../../docs/config/environments.md)
- [../../docs/architecture/deployment.md](../../docs/architecture/deployment.md)
