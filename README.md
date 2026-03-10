# StyleUs

StyleUs is a wardrobe cataloging app with an AI-assisted review flow. The current product flow is:

1. Upload a garment image.
2. Finalize the upload through the API.
3. Run local AI enrichment for category, colors, and tags.
4. Review the suggestions, accept or edit them, and save the item.

The repository is a small monorepo with a React frontend and a FastAPI backend. The repo is now prepared for a split database strategy: local development still uses Docker Postgres, while hosted environments can point the backend at Supabase Postgres without changing the ORM or migration flow.

## Repository layout

- `apps/web` - Vite + React + TypeScript client with Tailwind, React Router, Zustand, and MSW.
- `services/api` - FastAPI + SQLAlchemy + Alembic API with uploads, local media serving, seeding, and embedded AI classification.
- `docs` - architecture, environment, and product notes.
- `dev.sh` - local launcher for Postgres, migrations, API, and web app.

## What is implemented today

- Wardrobe list, search, filter, detail, edit, and soft delete flows.
- Upload flow with local uploads or S3 presigned uploads.
- Upload review screen with AI preview, confidence bars, accept, edit, and cancel actions.
- Background AI enrichment for category, subcategory, colors, materials, style tags, and top tags.
- Local media variants (`orig`, `medium`, `thumb`) plus stored image metadata.
- Deterministic local seed dataset for demo and development.

The `Outfits` page and most settings are still placeholders. Supabase Auth, Supabase Storage, and a separate background worker are planned for later migration phases and are not implemented yet.

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
- starts the web app on `http://localhost:5173`.

Useful repo-level commands:

```bash
make db-up
make db-down
make lint
make test
make typecheck
```

## Environment model

The repo now treats environments explicitly as:

- `local` - developer workstation with Docker Postgres, local media, auto-migrations, and optional auto-seeding.
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
- Future background worker -> Render worker service
- Database/Auth/Storage -> Supabase

That target architecture is documented here:

- [docs/architecture/deployment.md](docs/architecture/deployment.md)
- [docs/config/environments.md](docs/config/environments.md)

## Runtime flow today

### Upload flow

1. The frontend calls `POST /items/presign`.
2. The API creates a placeholder wardrobe item.
3. The frontend uploads bytes to either:
   - a local API upload endpoint, or
   - an S3 presigned URL.
4. The frontend calls `POST /items/{item_id}/complete-upload`.
5. The API generates normalized image variants, stores metadata, and schedules AI classification.

### Review flow

1. The frontend navigates to `/upload/review/:id`.
2. It loads the uploaded item and requests `GET /items/{id}/ai-preview`.
3. The review page shows AI suggestions and confidence data.
4. The user accepts predictions, edits fields manually, or cancels the placeholder item.

### AI flow

- The API runs color extraction plus a local CLIP-based classifier when available.
- If CLIP is unavailable, the pipeline falls back to deterministic heuristics.
- Category and subcategory writes are thresholded.
- The worker split is planned later; the API currently uses FastAPI `BackgroundTasks`.

## What changes in later phases

Still not part of the current repository implementation:

- adding Supabase Auth
- migrating uploads to Supabase Storage
- introducing the Render worker
- production deployment rollout

## Further reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/config/environments.md](docs/config/environments.md)
- [docs/architecture/deployment.md](docs/architecture/deployment.md)
- [recap.md](recap.md)
