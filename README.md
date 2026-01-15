# StyleUs – AI Fashion Companion

StyleUs is a local-first wardrobe companion: upload garments, get AI-suggested categories/colors/tags instantly, review them, and keep everything in sync between a modern React client and a FastAPI API on PostgreSQL.

## Monorepo layout
- `apps/web` – Vite + React + TypeScript + Tailwind client (React Router, Zustand, MSW for mocks).
- `services/api` – FastAPI + SQLAlchemy + Alembic API with local AI enrichment and PostgreSQL (Docker).
- `docs` – Product and technical documentation, including `docs/tech-stack.md` for current stack choices.

## Quickstart
From the repo root, start everything with one command:
```bash
./dev.sh
# or: make dev
```
What it does:
- Checks for Docker (and that it is running), Node/npm, and Python 3.11+.
- Creates/updates `services/api/.venv` and installs backend deps.
- Ensures `.env` files exist (`services/api/.env`, `apps/web/.env.local`) and loads backend env vars.
- Starts PostgreSQL in Docker (`styleus-db`) and waits for it to be healthy.
- Applies Alembic migrations, then starts the FastAPI API on http://localhost:8000.
- Installs frontend deps (if needed) and starts the Vite dev server on http://localhost:5173.

Existing individual commands (e.g., `make run`, `npm run dev`) still work for advanced use.

### Quality checks
```bash
make lint          # Ruff + Prettier
make test          # pytest + vitest run
make typecheck     # mypy + tsc --noEmit
```

## Troubleshooting
- Docker not running: start Docker Desktop/daemon, then rerun `./dev.sh`.
- Port already in use: update the port mapping in `services/api/docker-compose.yml` (e.g., `5433:5432`) and adjust `DATABASE_URL`; pass `--port` to Vite if 5173 is taken.
- Database reset: stop the stack (Ctrl+C), run `make db-down` to remove the container, and rerun `./dev.sh` (data lives in the `styleus-pgdata` volume unless you remove it).
- Migrations failing: ensure Postgres is up (`docker ps`), then run `cd services/api && .venv/bin/alembic upgrade head`; if revisions are out of sync, remove the container/volume and rerun `./dev.sh`.
