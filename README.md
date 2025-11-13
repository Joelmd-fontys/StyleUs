# StyleUs – AI Fashion Companion

StyleUs is an AI-assisted wardrobe companion composed of a FastAPI backend, a Vite + React web client, and shared tooling for tests, docs, and infrastructure.

## Quickstart

### Backend (FastAPI + PostgreSQL)

```bash
cd services/api
cp .env.example .env
make setup      # install Python deps
make db-up      # start postgres via Docker (optional helper)
make run        # launches FastAPI on http://127.0.0.1:8000
```

See [services/api/README.md](services/api/README.md) for Docker Compose, seeding, migrations, and available Make targets.

### Frontend (Vite + React)

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev     # opens http://127.0.0.1:5173
```

Feature flags for API vs. MSW mocks live in `.env.local`. Full details live in [apps/web/README.md](apps/web/README.md).

### Tests & Quality

- Frontend: `cd apps/web && npm run typecheck && npx vitest run`
- Backend: `cd services/api && make lint && pytest`

Root-level `tests/` hosts cross-cutting suites; each subdirectory contains its own README.

## Reference Docs

- Product overview: [docs/prd](docs/prd/README.md)
- Iteration status & scope: [docs/scope](docs/scope/iteration-1.md)
- Infrastructure notes: [docs/infra](docs/infra/README.md) (when applicable)
