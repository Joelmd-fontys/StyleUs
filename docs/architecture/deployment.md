# Deployment Architecture

This document describes the intended production platform split for StyleUs. It is a planning and repository-foundation document for the migration path; it does not mean every hosted integration is already implemented.

## Target platform layout

```text
Browser
-> Frontend SPA (Vercel)
-> FastAPI API (Render web service)
-> Supabase Postgres

Browser
-> direct public frontend configuration from Vercel

FastAPI API
-> Supabase Postgres
-> Supabase Storage
-> Supabase Auth token validation

FastAPI API
-> Render worker enqueue boundary

Render worker
-> background AI processing via ai_jobs queue
```

## Platform responsibilities

### Vercel

Owns:

- static hosting for the React/Vite frontend
- public frontend environment variables
- preview and production frontend deployments

Should expose only browser-safe variables such as:

- `VITE_APP_ENV`
- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

### Render web service

Owns:

- FastAPI runtime
- backend private environment variables
- API request handling
- upload finalization
- business logic and item persistence

Should own private variables such as:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_JWT_AUDIENCE`
- storage credentials
- AI pipeline configuration

### Render worker

Owns:

- durable background job processing
- AI enrichment outside the request lifecycle
- writes back item predictions after polling Postgres

The repository now includes the worker runtime and queue model. Provisioning the actual hosted Render worker service is still a later deployment step.

### Supabase

Planned target owner for:

- PostgreSQL database
- authentication
- storage

The repository should prepare for Supabase as infrastructure, but business data access and authorization logic still stay in the Python backend.

## Boundary rules

### What the frontend may know directly

- API base URL
- public app environment
- later, public Supabase client configuration for auth/session bootstrap

### What must stay backend-only

- database credentials
- service-role or admin keys
- storage write credentials
- internal AI configuration
- migration and seeding controls

### What remains local-only today

- Docker-managed Postgres for local development
- local upload mode and local media serving
- automatic startup migrations and startup seeding by default
- MSW toggles for mock API behavior

## Current state vs later phases

Implemented now:

- frontend and backend are explicitly environment-aware
- startup mutation is config-gated
- docs reflect the Vercel + Render + Supabase target split
- the backend can now point `DATABASE_URL` at Supabase Postgres while keeping SQLAlchemy and Alembic unchanged
- the frontend can sign in with Supabase Auth and send bearer tokens to FastAPI
- FastAPI validates Supabase JWTs and maps `sub` to the application user ID
- Supabase Storage-backed upload finalization plus a Postgres-backed `ai_jobs` worker flow are implemented
- the API now enqueues AI work and the dedicated worker performs enrichment asynchronously

Later phases will implement:

- actual hosted deployment rollout
