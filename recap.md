# Recap

## What’s live
- **Frontend:** Vite + React + TypeScript + Tailwind with React Router screens (dashboard, wardrobe list/detail, upload review, settings), Zustand store, and MSW mocks behind feature flags. Upload panel flows through presign → PUT upload → completion and routes to the AI-assisted review screen.
- **Backend:** FastAPI + SQLAlchemy + Alembic on PostgreSQL (Docker). Endpoints for health/version/items, presign/upload/complete-upload, AI preview, and background classification (local CLIP + heuristics) with media served from `MEDIA_ROOT`.
- **Tooling:** Root `Makefile` for `db-up/db-down/run/lint/test/typecheck`, Ruff + mypy on the API, Prettier + tsc + Vitest on the web app, and refreshed `.env.example` files plus `docs/tech-stack.md` outlining stack decisions.
- **Data/Media:** Local uploads live under `services/api/media` (gitignored) with seeding available via `make seed` / `make reset-seed`.

## Simplifications just completed
- Removed unused scaffolding directories (config/infrastructure/data/scripts/packages/tests/services/ai) and the stray `styleus_api.egg-info` artefact; trimmed unused deps (`httpx`, `@testing-library/user-event`).
- Added Prettier (with `npm run lint/format`) and made `npm test` use `vitest run`; MSW now only starts when mocks are enabled.
- Added root Makefile wrappers, updated READMEs, and documented new AI env knobs (`AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`, `AI_DEVICE`).

## Known gaps / risks
- Tests were not executed in this pass; run `make test` and `npm test` after installing dependencies.
- Frontend test coverage is still limited (upload review); broader flows rely on manual verification.
- Local media can grow quickly; clear `services/api/media` periodically if disk space is constrained.
