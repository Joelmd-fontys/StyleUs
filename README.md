# StyleUs

StyleUs is a wardrobe cataloging app with an AI-assisted review flow. The current product flow is:

1. Upload a garment image.
2. Finalize the upload through the API.
3. Enqueue AI enrichment and process it in a dedicated worker.
4. Review the suggestions as they arrive, accept or edit them, and save the item.

The repository is a small monorepo with a React frontend and a FastAPI backend. The repo now supports a split infrastructure model: local development still uses Docker Postgres and can keep a local-only auth bypass, while hosted environments are expected to use Supabase Postgres plus Supabase Auth without changing the ORM or migration flow.

## Repository layout

- `apps/web` - Vite + React + TypeScript client with Tailwind, React Router, Zustand, and MSW.
- `services/api` - FastAPI + SQLAlchemy + Alembic API plus a dedicated AI worker using the same Postgres-backed queue.
- `docs` - architecture, environment, and product notes.
- `dev.sh` - local launcher for Postgres, migrations, API, AI worker, and web app.

## What is implemented today

- Wardrobe list, search, filter, detail, edit, and soft delete flows.
- Upload flow with API-issued Supabase signed upload targets.
- Upload review screen with AI preview, confidence bars, accept, edit, and cancel actions.
- Durable AI job queue plus worker-driven enrichment for category, subcategory, colors, materials, style tags, and top tags.
- Private Supabase Storage variants (`orig`, `medium`, `thumb`) plus stored image metadata and signed read URLs.
- Deterministic local seed dataset for demo and development.
- Supabase Auth in the frontend plus bearer-token validation in the FastAPI API.

The `Outfits` page and most settings are still placeholders.

## Local quickstart

Start the whole stack from the repo root:

```bash
./dev.sh
# or
make dev
```

This script:

- verifies Docker, Node/npm, and Python 3.11+;
- creates or refreshes `services/api/.venv`;
- ensures `services/api/.env` and `apps/web/.env.local` exist;
- starts Postgres in Docker as `styleus-db`;
- applies Alembic migrations;
- starts the API on `http://localhost:8000`;
- starts the AI worker in the background;
- starts the web app on `http://localhost:5173`.

Live uploads require real Supabase Auth/Storage values in `services/api/.env` and `apps/web/.env.local`. Without those values, the app can still run locally, but the direct-upload storage path will not work.

Useful repo-level commands:

```bash
make db-up
make db-down
make worker
make lint
make test
make typecheck
```

## Environment model

The repo now treats environments explicitly as:

- `local` - developer workstation with Docker Postgres, Supabase Auth/Storage wiring, auto-migrations, and optional auto-seeding.
- `staging` - pre-production deployment with production-like infrastructure and safe startup defaults.
- `production` - public deployment with the same safe startup defaults as staging.

Local files:

- `apps/web/.env.local`
- `services/api/.env`

Service examples:

- `apps/web/.env.example`
- `services/api/.env.example`

Staging and production env vars are intended to live in platform-managed secret stores, not in committed files:

- Vercel for `apps/web`
- Render for `services/api`

See [docs/config/environments.md](docs/config/environments.md) for the full environment matrix.

### Auth behavior by environment

- `local` can still use `LOCAL_AUTH_BYPASS=true` on the API for the existing guest-style workflow.
- `local` can also use real Supabase Auth by setting:
  - `apps/web/.env.local` -> `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`
  - `services/api/.env` -> `SUPABASE_URL`
- the fallback local identity and seeded demo wardrobe are confined to `APP_ENV=local`
- `staging` and `production` require real Supabase bearer tokens and do not fall back to the local bypass.

### Supabase Auth setup

Minimum manual setup in the Supabase dashboard:

1. Open Authentication -> Sign In / Providers and enable Email.
2. Decide whether Confirm email should stay enabled for new signups.
3. Open Authentication -> URL Configuration and set:
   - Site URL: your active frontend origin, for example `http://127.0.0.1:5173` locally
   - Additional Redirect URLs: every SPA origin you plan to use, including local, staging, and production
4. Copy the project URL into:
   - `VITE_SUPABASE_URL` for the frontend
   - `SUPABASE_URL` for the backend
5. Copy the public browser key into `VITE_SUPABASE_PUBLISHABLE_KEY`.
   - `VITE_SUPABASE_ANON_KEY` still works as a legacy alias if your project has not moved to publishable keys yet.
6. If your Supabase project still signs access tokens with the legacy shared secret instead of asymmetric keys, also set `SUPABASE_PUBLISHABLE_KEY` on the backend.

### Supabase Storage setup

Minimum manual setup in the Supabase dashboard:

1. Open Storage and create a private bucket, for example `wardrobe-images`.
2. Set the bucket file size limit to match `MEDIA_MAX_UPLOAD_SIZE` on the API.
3. Restrict allowed MIME types to `image/jpeg`, `image/png`, and `image/webp`.
4. Copy the bucket name into `SUPABASE_STORAGE_BUCKET`.
5. Copy the service-role key into `SUPABASE_SERVICE_ROLE_KEY` on the backend only.
6. Keep the bucket private. The app now serves image reads through temporary signed URLs only.

## Database strategy

The backend continues to use:

- SQLAlchemy for runtime data access
- Alembic for schema migrations
- `DATABASE_URL` as the single database connection input

Database hosting now works in two modes:

- `local` -> Docker Postgres remains the default developer database
- `staging` / `production` -> `DATABASE_URL` can point to Supabase Postgres

The application normalizes `postgres://` and `postgresql://` URLs to the `psycopg` SQLAlchemy driver automatically, so Supabase connection strings can be used directly.

For hosted environments:

- use a direct Supabase connection or Supavisor session pooling
- keep `sslmode=require` in the connection string
- keep Alembic as the only schema migration path
- avoid transaction-pool mode for the API and Alembic in this phase

## Startup safety

The backend now uses explicit startup gates:

- `RUN_MIGRATIONS_ON_START`
- `RUN_SEED_ON_START`

Defaults:

- `APP_ENV=local` -> both default to `true`
- `APP_ENV=staging|production` -> both default to `false`

This preserves local convenience while making hosted environments safe by default. Seeding remains available for local work; startup seeding and migration behavior must be opted into explicitly outside local development.

## Planned deployment architecture

The intended production platform split is:

- Frontend -> Vercel
- API -> Render web service
- Background worker -> Render worker service
- Database/Auth/Storage -> Supabase

That target architecture is documented here:

- [docs/architecture/deployment.md](docs/architecture/deployment.md)
- [docs/config/environments.md](docs/config/environments.md)

## Runtime flow today

### Upload flow

1. The frontend calls `POST /items/presign`.
2. The API creates a placeholder wardrobe item.
3. The frontend uploads the source image directly to a private Supabase Storage object using the signed upload target.
4. The frontend calls `POST /items/{item_id}/complete-upload`.
5. The API downloads the private source object, generates normalized image variants, stores private object paths plus metadata, and inserts a pending `ai_jobs` row.
6. The worker polls the queue, runs AI enrichment, and writes predictions back to the item.

### Review flow

1. The frontend navigates to `/upload/review/:id`.
2. It loads the uploaded item and requests `GET /items/{id}/ai-preview`.
3. The review page shows persisted AI suggestions or a pending state while it polls for completion.
4. The user accepts predictions, edits fields manually, or cancels the placeholder item.

### AI flow

- The API only enqueues work; it no longer runs heavy AI inference in the request lifecycle.
- The worker claims jobs with Postgres row locking (`SELECT ... FOR UPDATE SKIP LOCKED`).
- The worker runs color extraction plus a local CLIP-based classifier when available.
- If CLIP is unavailable, the pipeline falls back to deterministic heuristics.
- Category and subcategory writes are thresholded.
- `GET /items/{id}/ai-preview` returns persisted predictions plus job state; it does not run a fresh pipeline pass.

## What changes in later phases

Still not part of the current repository implementation:

- production deployment rollout

## Further reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/config/environments.md](docs/config/environments.md)
- [docs/architecture/deployment.md](docs/architecture/deployment.md)
- [recap.md](recap.md)
