# Environment Model

StyleUs now treats environment handling as a first-class concern across the web app and API.

## Environment tiers

| Environment | Purpose | Frontend runtime | Backend runtime | Startup defaults |
| --- | --- | --- | --- | --- |
| `local` | developer workstations | Vite dev server | FastAPI on host machine | migrations `on`, seed `on` |
| `staging` | pre-production verification | Vercel preview or staging project | Render web service | migrations `off`, seed `off` |
| `production` | public deployment | Vercel production project | Render web service | migrations `off`, seed `off` |

## Local files vs hosted secrets

Local development uses checked-in examples copied into local files:

- `apps/web/.env.example` -> `apps/web/.env.local`
- `services/api/.env.example` -> `services/api/.env`

Hosted environments should use platform-managed configuration:

- Vercel environment variables for `apps/web`
- Render environment variables for `services/api`
- Supabase project configuration for database, auth, and storage

Do not commit staging or production secrets into the repository.

## Frontend variables

These variables are browser-visible and must remain safe to expose publicly.

| Variable | Used now | Intended owner | Notes |
| --- | --- | --- | --- |
| `VITE_APP_ENV` | yes | Vercel / local `.env.local` | `local`, `staging`, `production` |
| `VITE_API_BASE_URL` | yes | Vercel / local `.env.local` | base URL for FastAPI; defaults to localhost only in `local` |
| `VITE_USE_LIVE_API_ITEMS` | yes | local `.env.local` | local development toggle for MSW vs live API |
| `VITE_USE_LIVE_API_UPLOAD` | yes | local `.env.local` | local development toggle for uploads |
| `VITE_SUPABASE_URL` | not yet | Vercel | reserved for future Supabase Auth integration |
| `VITE_SUPABASE_ANON_KEY` | not yet | Vercel | reserved for future Supabase Auth integration |

Notes:

- The two `VITE_USE_LIVE_API_*` flags are local-development controls. They are not expected to matter in production.
- Supabase frontend variables are documented now, but later migration phases will decide when they become active.

## Backend variables

These variables are server-side and must remain private.

| Variable | Used now | Intended owner | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | yes | Render / local `.env` | `local`, `staging`, `production` |
| `APP_VERSION` | yes | Render / local `.env` | surfaced by health/version endpoints |
| `DATABASE_URL` | yes | Render / local `.env` | local Docker Postgres in `local`; Supabase Postgres in hosted envs |
| `API_KEY` | yes | Render / local `.env` | temporary secure-env guard until real auth lands |
| `CORS_ORIGINS` | yes | Render / local `.env` | comma-separated origins |
| `UPLOAD_MODE` | yes | Render / local `.env` | `local` or `s3`; later phases will revisit storage |
| `MEDIA_ROOT` / `MEDIA_URL_PATH` | yes | local `.env` / Render | current local-media settings |
| `MEDIA_MAX_UPLOAD_SIZE` | yes | Render / local `.env` | upload cap |
| `RUN_MIGRATIONS_ON_START` | yes | Render / local `.env` | default `true` in local, `false` otherwise |
| `RUN_SEED_ON_START` | yes | local `.env` / Render | default `true` in local, `false` otherwise |
| `AWS_REGION` / `S3_BUCKET_NAME` | yes | Render / local `.env` | current S3-mode support |
| `AI_*` | yes | Render / local `.env` | current classifier and color pipeline knobs |
| `SEED_LIMIT` / `SEED_KEY` | yes | local `.env` / Render | deterministic seed controls |

`SEED_ON_START` is still accepted as a legacy alias for `RUN_SEED_ON_START`, but new environments should use the new name.

## Database strategy

The backend still has a single database configuration input: `DATABASE_URL`.

Supported usage in this phase:

- `local` -> Docker Postgres
- `staging` / `production` -> Supabase Postgres

The backend continues to own all business data access through SQLAlchemy. Supabase is treated only as the PostgreSQL host in this phase.

### Connection-string guidance

- Prefer `postgresql+psycopg://...` when writing URLs manually.
- `postgres://...` and `postgresql://...` are accepted and normalized automatically.
- Use `sslmode=require` for hosted Supabase connections.
- For the API service and Alembic, use either:
  - a direct Supabase database connection, or
  - Supavisor session pooling
- Do not use transaction pooling for the FastAPI app or Alembic in this phase.

### Migration rule

Alembic remains the only schema migration path. Running migrations against Supabase still means:

```bash
cd services/api
export DATABASE_URL='...'
make upgrade
```

No Supabase-specific schema tool is introduced in this repository.

## Startup rules

The backend startup lifecycle now follows these rules:

- Local may auto-run migrations and seed data for convenience.
- Staging and production do not auto-run migrations by default.
- Staging and production do not auto-seed by default.
- Any hosted startup mutation must be an explicit decision through env configuration.

This keeps local development ergonomic while preventing unsafe startup side effects in hosted environments.

## Platform ownership

| Concern | Platform |
| --- | --- |
| Frontend static hosting | Vercel |
| Frontend public env vars | Vercel |
| FastAPI runtime | Render |
| Future worker runtime | Render |
| Database | Supabase |
| Auth | Supabase |
| Storage | Supabase |
| Backend private secrets | Render |

## What remains for later phases

This document only establishes the environment model. It does not implement:

- Supabase Auth
- Supabase Storage
- worker processes
- deployment rollout
