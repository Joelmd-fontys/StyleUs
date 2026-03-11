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
| `VITE_SUPABASE_URL` | yes | Vercel / local `.env.local` | public Supabase project URL for browser auth and direct signed uploads |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | yes | Vercel / local `.env.local` | preferred public browser key for Supabase Auth |
| `VITE_SUPABASE_ANON_KEY` | yes | Vercel / local `.env.local` | public fallback key name still accepted for compatibility |
| `VITE_USE_LIVE_API_ITEMS` | yes | local `.env.local` | local development toggle for MSW vs live API |
| `VITE_USE_LIVE_API_UPLOAD` | yes | local `.env.local` | local development toggle for uploads |

Notes:

- The two `VITE_USE_LIVE_API_*` flags are local-development controls. They are not expected to matter in production.
- If both Supabase frontend variables are present and live API mode is enabled, the SPA requires a real Supabase session before it renders the app shell.
- If they are absent in `local`, the SPA stays in explicit guest mode and relies on the API's local auth bypass.

## Backend variables

These variables are server-side and must remain private.

| Variable | Used now | Intended owner | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | yes | Render / local `.env` | `local`, `staging`, `production` |
| `APP_VERSION` | yes | Render / local `.env` | surfaced by health/version endpoints |
| `DATABASE_URL` | yes | Render / local `.env` | local Docker Postgres in `local`; Supabase Postgres in hosted envs |
| `SUPABASE_URL` | yes | Render / local `.env` | Supabase project URL used for auth verification and Storage API calls |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Render / local `.env` | backend-only key for private Storage operations |
| `SUPABASE_STORAGE_BUCKET` | yes | Render / local `.env` | private bucket for wardrobe uploads and variants |
| `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_ANON_KEY` | optional | Render / local `.env` | only needed for legacy shared-secret Supabase JWT verification |
| `SUPABASE_JWT_AUDIENCE` | yes | Render / local `.env` | expected access-token audience, normally `authenticated` |
| `LOCAL_AUTH_BYPASS` | yes | local `.env` | explicit local-only auth bypass; invalid in hosted envs |
| `LOCAL_AUTH_USER_ID` / `LOCAL_AUTH_EMAIL` | yes | local `.env` | identity used when local bypass is enabled |
| `CORS_ORIGINS` | yes | Render / local `.env` | comma-separated origins |
| `MEDIA_MAX_UPLOAD_SIZE` | yes | Render / local `.env` | upload cap |
| `SUPABASE_SIGNED_URL_TTL_SECONDS` | optional | Render / local `.env` | signed-read TTL for `imageUrl`, `mediumUrl`, and `thumbUrl` |
| `MEDIA_ROOT` | yes | local `.env` / Render | local scratch/cache directory still used by image and AI helpers |
| `RUN_MIGRATIONS_ON_START` | yes | Render / local `.env` | default `true` in local, `false` otherwise |
| `RUN_SEED_ON_START` | yes | local `.env` / Render | default `true` in local, `false` otherwise |
| `AI_*` | yes | Render / local `.env` | current classifier and color pipeline knobs |
| `SEED_LIMIT` / `SEED_KEY` | yes | local `.env` / Render | deterministic seed controls |

`SEED_ON_START` is still accepted as a legacy alias for `RUN_SEED_ON_START`, but new environments should use the new name.

Auth rules:

- `APP_ENV` is required. The backend no longer defaults to `local` when it is missing.
- `staging` and `production` require `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`.
- `local` can boot without the Storage variables, but live uploads and signed image reads will not work until they are set.
- `SUPABASE_PUBLISHABLE_KEY` is only required when the Supabase project still uses legacy shared-secret JWT signing.
- `LOCAL_AUTH_BYPASS` is only valid in `local`.
- `LOCAL_AUTH_USER_ID` and `LOCAL_AUTH_EMAIL` are only used in `local`, including the deterministic seed workflow.
- All business data access still goes through FastAPI, even though the browser now authenticates directly with Supabase.

## Database strategy

The backend still has a single database configuration input: `DATABASE_URL`.

Supported usage in this phase:

- `local` -> Docker Postgres
- `staging` / `production` -> Supabase Postgres

The backend continues to own all business data access through SQLAlchemy. Supabase is treated as the PostgreSQL host plus the private object store in this phase.

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

The deterministic seed commands are also local-only. They reuse the configured local auth identity and now fail if `APP_ENV` is not `local`.

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

- worker processes
- deployment rollout
