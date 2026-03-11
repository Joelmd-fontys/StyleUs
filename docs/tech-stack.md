# Tech Stack Decision

## What we use today
- Frontend: React 18 + Vite + TypeScript with Tailwind for styling, React Router for navigation, Zustand for state, MSW for optional local mocks, Vitest + Testing Library for tests, and `tsc --noEmit` for type checks.
- Backend: FastAPI + Uvicorn with SQLAlchemy 2.0 ORM, Alembic migrations, Pydantic settings, PostgreSQL (Docker via Compose) as the sole database, JSON logging, a Postgres-backed AI worker, and a local-first AI pipeline (Pillow, NumPy, scikit-learn, optional open-clip/torch/ONNX) embedded in the API service.
- Tooling: Ruff for Python linting, mypy for Python type checks, pytest for backend tests, service-level Make targets, and `.env.example` files per app. Static assets and local media are served from `services/api/media` and ignored by git.

## Redundant or overlapping pieces
- Previously unused scaffolding directories (`config/`, `packages/`, `scripts/`, `data/`, `infrastructure/`, root-level `tests/`) only contained placeholder README files and were not referenced by the apps.
- `services/ai/` duplicated the AI concept while the active pipeline lives inside `services/api/app/ai/`.
- A built `styleus_api.egg-info/` directory was checked in even though dependencies are installed in editable mode.
- Frontend lacked a declared lint/format standard; everything else already has a single tool.

## What we removed or merged
- Deleted the unused scaffolding directories and empty test folders to reduce noise.
- Dropped the unused `services/ai/` placeholder and the tracked `styleus_api.egg-info/` artefact.
- Standardized frontend lint/format on Prettier (formatting) plus TypeScript type checks; avoided introducing ESLint/Biome to keep dependencies minimal.
- Kept MSW as the single mocking approach (toggled by env flags) and continue to lean on Tailwind components instead of introducing a UI kit.

## Standards to keep going forward
- Database: PostgreSQL via Docker Compose for local dev.
- Backend: FastAPI + SQLAlchemy + Alembic + Pydantic settings, JSON logging, a dedicated AI worker backed by Postgres polling, and the embedded local-first AI pipeline (no external AI APIs).
- Frontend: React + Vite + TypeScript + Tailwind with React Router and Zustand; MSW for mocks when live API is disabled.
- Testing: pytest for backend; Vitest + Testing Library for frontend (no parallel frameworks).
- Lint/format: Ruff for Python; Prettier for frontend formatting with `tsc --noEmit` for type safety.
- Tooling commands: keep Make targets for db-up/db-down/run/lint/test on the API and simple `npm run dev/typecheck/test` scripts for the web app.
