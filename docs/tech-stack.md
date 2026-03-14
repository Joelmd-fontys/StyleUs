# Tech Stack

## Web

- React 18
- Vite
- TypeScript
- React Router
- Zustand
- Tailwind CSS
- MSW for local mock mode
- Vitest and Testing Library

## API

- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Pydantic Settings
- PyJWT for Supabase token verification

## AI processing

- Postgres-backed `ai_jobs` queue polled by an embedded FastAPI worker loop
- Pillow
- NumPy
- scikit-learn
- `open-clip-torch` with optional ONNX inference

## Tooling

- `dev.sh` and Make targets for local orchestration
- Ruff and mypy for Python checks
- Prettier for frontend formatting
- `tsc --noEmit` for frontend type checks
- pytest for backend tests
