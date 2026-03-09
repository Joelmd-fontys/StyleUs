# StyleUs

StyleUs is a local-first wardrobe cataloging app. The current product flow is:

1. Upload a garment image.
2. Let the API finalize the upload and run local AI enrichment.
3. Review AI-suggested category, colors, and tags.
4. Accept or edit the result and save it into the wardrobe.

The repository is organized as a small monorepo with a React frontend and a FastAPI backend backed by PostgreSQL.

## Repository layout

- `apps/web` – Vite + React + TypeScript client with Tailwind, React Router, Zustand, and MSW.
- `services/api` – FastAPI + SQLAlchemy + Alembic API with upload handling, local media serving, seeding, and embedded AI classification.
- `docs` – supporting product and technical notes.
- `dev.sh` – root development launcher that brings up Postgres, applies migrations, and starts both app processes.

## What is implemented

- Wardrobe list, search, filter, detail, edit, and soft delete flows.
- Upload flow with local uploads or S3 presigned uploads.
- Upload review screen with AI preview, confidence bars, accept, edit, and cancel actions.
- Background AI enrichment for category, subcategory, colors, materials, style tags, and top tags.
- Local media variants (`orig`, `medium`, `thumb`) plus stored image metadata.
- Deterministic local seed dataset for demo and development.

The `Outfits` page and most settings are still placeholders; they are present in the UI but not built out into full product features yet.

## Quickstart

Start the whole stack from the repo root:

```bash
./dev.sh
# or
make dev
```

This script:

- verifies Docker, Node/npm, and Python 3.11+;
- creates or refreshes `services/api/.venv`;
- ensures `services/api/.env` and `apps/web/.env.local` exist;
- starts Postgres in Docker as `styleus-db`;
- applies Alembic migrations;
- starts the API on `http://localhost:8000`;
- starts the web app on `http://localhost:5173`.

## Local development commands

From the repo root:

```bash
make db-up
make db-down
make lint
make test
make typecheck
```

Service-specific commands still work directly inside `apps/web` and `services/api`.

## Runtime flow

### Upload flow

1. The frontend calls `POST /items/presign`.
2. The API creates a placeholder wardrobe item and returns either:
   - a local API upload target at `/items/uploads/{item_id}`, or
   - an S3 presigned PUT URL.
3. The frontend uploads the image bytes.
4. The frontend calls `POST /items/{item_id}/complete-upload`.
5. The API generates normalized image variants, stores metadata, and schedules background AI classification.

### Review flow

1. The frontend navigates to `/upload/review/:id`.
2. It loads the uploaded item and requests `GET /items/{id}/ai-preview`.
3. The review page shows AI suggestions and confidence data.
4. The user either:
   - accepts predictions and saves them, or
   - edits fields and confirms manually, or
   - cancels, which deletes the placeholder item.

### AI flow

- The API runs color extraction plus a local CLIP-based classifier when available.
- If CLIP is unavailable, the pipeline falls back to deterministic heuristics.
- Category/subcategory predictions are only written back when they clear configured thresholds.
- Color extraction uses foreground masking before LAB/KMeans clustering when enabled.

## Configuration

The root `.env.example` is intentionally informational only. Actual service env files live at:

- `apps/web/.env.example`
- `services/api/.env.example`

Most useful backend knobs during development:

- `UPLOAD_MODE=local|s3`
- `MEDIA_ROOT`
- `AI_ENABLE_CLASSIFIER`
- `AI_CONFIDENCE_THRESHOLD`
- `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`
- `AI_COLOR_USE_MASK`
- `AI_COLOR_MASK_METHOD`
- `AI_COLOR_MIN_FOREGROUND_PIXELS`

## Notes on Docker and Postgres

- Docker Compose in `services/api/docker-compose.yml` provisions Postgres only.
- The API itself runs directly on the host during normal local development.
- The Postgres container uses the persistent `styleus-pgdata` volume.

## Quality checks

```bash
make lint
make test
make typecheck
```

- Backend: Ruff, pytest, mypy
- Frontend: Prettier, Vitest, `tsc --noEmit`

## Further reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/tech-stack.md](docs/tech-stack.md)
- [recap.md](recap.md)
