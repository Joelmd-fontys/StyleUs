# Deployment Architecture

StyleUs is structured for a simple hosted split:

- frontend on Vercel
- API on Render
- worker on Render
- Postgres, Auth, and Storage on Supabase

## Responsibilities

Vercel:

- serves the built SPA
- owns public browser env vars
- exposes only browser-safe values such as `VITE_APP_ENV`, `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY`

Render web service:

- runs FastAPI
- owns backend secrets and private env vars
- finalizes uploads, serves signed media URLs, and handles all business logic

Render worker:

- runs `app/worker.py`
- polls `ai_jobs`
- writes AI predictions back to items

Supabase:

- hosts Postgres
- issues auth tokens
- stores private uploaded media

## Boundary rules

The frontend may know:

- API base URL
- public Supabase URL
- public Supabase browser key
- local mock flags during development

The frontend must not know:

- `DATABASE_URL`
- service-role keys
- storage write credentials
- worker configuration
- migration or seed controls

## Local versus hosted

- `local` uses Docker Postgres, optional auth bypass, and startup convenience defaults
- `staging` and `production` should use platform-managed env vars and leave startup mutation disabled by default

The deployment target is documented here so the repository stays aligned before infrastructure automation is added.
