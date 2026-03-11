# Recap

## What was cleaned up

- The backend database configuration now cleanly supports both local Docker Postgres and Supabase Postgres without changing the FastAPI, SQLAlchemy, or Alembic stack.
- Alembic configuration was clarified so migrations continue to read from the same `DATABASE_URL` as the application.
- The backend test harness was loosened so pure config tests no longer require a live Postgres instance just to run.
- The prototype auth stub was replaced with Supabase Auth in the browser plus JWT validation in FastAPI.

## What was simplified

- `DATABASE_URL` remains the single database input for the backend in every environment.
- Supabase-provided `postgres://` and `postgresql://` URLs are normalized automatically to the `psycopg` SQLAlchemy dialect.
- The local-vs-hosted database strategy is now explicit in the README and environment docs.
- User identity now comes from a single source of truth: the Supabase access token `sub`, which maps directly to the existing `users.id` UUID.
- Local development keeps an explicit bypass instead of an implicit global fake user.
- The deterministic seed workflow now reuses the configured local auth identity and is blocked outside `APP_ENV=local`.
- Hosted auth now verifies asymmetric tokens via JWKS and can fall back to Supabase user-info verification for legacy shared-secret projects.
- Uploads now go directly from the browser to private Supabase Storage through API-issued signed upload targets.
- Wardrobe items now persist private storage object paths, while API responses translate them into temporary signed image URLs.
- AI processing now runs through a durable Postgres-backed `ai_jobs` queue with a dedicated worker process.

## What was removed

- No product features or schema-management paths were removed in this phase.
- No local Docker Postgres workflow was removed.
- The secure-environment API key gate was removed in favor of real bearer-token auth.

## What remains potentially fragile

- Hosted worker deployment is still a manual later phase even though the runtime now exists in the repo.
- Supabase Storage now depends on manual dashboard configuration for the private bucket, MIME allow-list, and size limits.
- The backend integration tests that exercise real DB behavior still depend on a reachable Postgres instance.
