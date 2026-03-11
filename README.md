# StyleUs

StyleUs is a wardrobe cataloging app with an AI-assisted review flow. The repo contains a React web app, a FastAPI API, and a dedicated worker that processes background enrichment jobs.

## Repository layout

- `apps/web` - Vite + React + TypeScript client.
- `services/api` - FastAPI API, Alembic migrations, seed tools, and the AI worker.
- `docs` - cross-cutting architecture and environment notes.
- `dev.sh` - local launcher for Postgres, migrations, API, worker, and web app.

## System flow

1. The browser requests `POST /items/presign`.
2. The API creates a placeholder item and returns a signed upload target.
3. The browser uploads directly to private Supabase Storage.
4. `POST /items/{item_id}/complete-upload` creates image variants and enqueues an `ai_jobs` row.
5. `app/worker.py` claims queued jobs, runs the AI pipeline, and stores predictions.
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
- start the AI worker
- start the web app on `http://127.0.0.1:5173`

Useful repo-level commands:

```bash
make db-up
make db-down
make worker
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

- Vercel for `apps/web`
- Render for `services/api`

See [docs/config/environments.md](docs/config/environments.md) for the full variable list and environment rules.

## Deployment target

The intended hosted split is:

- frontend on Vercel
- API on Render
- AI worker on Render
- database, auth, and storage on Supabase

See [docs/architecture/deployment.md](docs/architecture/deployment.md).

## Further reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/architecture/README.md](docs/architecture/README.md)
- [docs/config/environments.md](docs/config/environments.md)
- [recap.md](recap.md)
