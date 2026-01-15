# StyleUs – AI Fashion Companion

StyleUs is a local-first wardrobe companion: upload garments, get AI-suggested categories/colors/tags instantly, review them, and keep everything in sync between a modern React client and a FastAPI API on PostgreSQL.

## Monorepo layout
- `apps/web` – Vite + React + TypeScript + Tailwind client (React Router, Zustand, MSW for mocks).
- `services/api` – FastAPI + SQLAlchemy + Alembic API with local AI enrichment and PostgreSQL (Docker).
- `docs` – Product and technical documentation, including `docs/tech-stack.md` for current stack choices.

## Quickstart
1) Backend
```bash
cp services/api/.env.example services/api/.env
make db-up                     # start Postgres in Docker
make run                       # launches FastAPI on http://127.0.0.1:8000
```
2) Frontend
```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev                    # opens http://127.0.0.1:5173
```
3) Quality checks
```bash
make lint          # Ruff + Prettier
make test          # pytest + vitest run
make typecheck     # mypy + tsc --noEmit
```
Stop the database when done with `make db-down`.

## Troubleshooting
- Docker not running: start Docker Desktop/daemon, then rerun `make db-up`.
- Port conflicts: change the mapped port in `services/api/docker-compose.yml` (e.g., `5433:5432`) and update `DATABASE_URL`; adjust Vite port with `--host --port` if 5173 is taken.
- Migrations: ensure Postgres is up, then run `cd services/api && alembic upgrade head`; if Alembic complains about revisions, delete stale containers/volumes and rerun `make db-up`.
