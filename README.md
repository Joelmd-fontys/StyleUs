# StyleUs

StyleUs is a wardrobe cataloging app with an AI-assisted review flow. The repo contains a React web app and a FastAPI backend that serves HTTP requests and runs the AI job worker loop in-process.

## Repository layout

- `apps/web` - Vite + React + TypeScript client.
- `services/api` - FastAPI API, Alembic migrations, seed tools, and the embedded AI worker runtime.
- `docs` - cross-cutting architecture and environment notes.
- `dev.sh` - local launcher for Postgres, migrations, API, and web app.

## System flow

1. The browser requests `POST /items/presign`.
2. The API creates a placeholder item and returns a signed upload target.
3. The browser uploads directly to private Supabase Storage.
4. `POST /items/{item_id}/complete-upload` creates image variants and enqueues an `ai_jobs` row.
5. The FastAPI process starts the background worker loop, which claims queued jobs, runs the AI pipeline, and stores predictions.
6. The review screen polls `GET /items/{id}/ai-preview`, then the user accepts or edits the result before saving.

## Local development

Start the full stack from the repo root:

```bash
./dev.sh
# or
make dev
```

`./dev.sh` will:

- create `services/api/.env` and `apps/web/.env.local` from the checked-in examples when missing
- create or refresh `services/api/.venv`
- start Docker Postgres
- run Alembic migrations
- start the API on `http://127.0.0.1:8000`
- start the web app on `http://127.0.0.1:5173`
- start the embedded AI worker inside the API process

Useful repo-level commands:

```bash
make db-up
make db-down
make lint
make test
make typecheck
```

## Environment files

Local files:

- `apps/web/.env.local`
- `services/api/.env`

Examples:

- `apps/web/.env.example`
- `services/api/.env.example`

Local guest mode still works with `APP_ENV=local` and `LOCAL_AUTH_BYPASS=true`. Real auth and live uploads require Supabase values in both app env files.

Hosted environments should keep secrets in the deployment platform:

- Vercel for browser-visible `VITE_*` values
- Render for API values

See [docs/config/environments.md](docs/config/environments.md) for the complete variable matrix.

## Deployment target

The deployable hosted split in this repo is:

- frontend on Vercel from `apps/web`
- API on Render as a web service from `services/api`, with the AI worker loop embedded in the FastAPI process
- database, auth, and storage on Supabase

Repo deployment files:

- `apps/web/vercel.json`
- `render.yaml`

## Hosted deployment

Frontend on Vercel:

1. Create a Vercel project with Root Directory `apps/web`.
2. Set `VITE_APP_ENV`, `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY`.
3. Deploy. `apps/web/vercel.json` keeps the Vite build output at `dist` and rewrites SPA routes to `index.html`.

Backend on Render:

1. Create services from `render.yaml` or mirror the same settings in the dashboard.
2. Set `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, and `CORS_ORIGINS` on the API service.
3. Let the API run `python -m alembic upgrade head` before startup.
4. Confirm the API health check succeeds at `/health`.

The deployed system flow stays the same as local:

1. user logs in with Supabase Auth
2. frontend uploads the source image to Supabase Storage
3. API finalizes the upload and creates the wardrobe row plus `ai_jobs` row
4. the embedded worker loop processes the job and writes predictions back to Postgres
5. frontend review screen polls until the AI result is ready

See [docs/architecture/deployment.md](docs/architecture/deployment.md) and [services/api/README.md](services/api/README.md) for the platform-specific details.

## Further reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/architecture/README.md](docs/architecture/README.md)
- [docs/config/environments.md](docs/config/environments.md)
- [recap.md](recap.md)
