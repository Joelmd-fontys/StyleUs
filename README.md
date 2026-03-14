# StyleUs

StyleUs is an AI-assisted wardrobe management app. Users upload clothing images, review AI-generated metadata, and build a structured digital wardrobe backed by FastAPI, Supabase, and a React web app.

## Live Demo

- Live App: https://style-us.vercel.app/
- API Health: https://styleus-api.onrender.com/health

In the live app, users can sign in, upload clothing photos, wait for AI analysis, and review or correct predicted categories, colors, and tags before saving items to their wardrobe.

## What This Project Does

StyleUs helps users catalog clothing without filling out every field manually. An uploaded image is stored in Supabase Storage, then processed by an AI pipeline that predicts category and subcategory, extracts dominant colors, and generates useful tags. The frontend presents those predictions in a review screen so the user can confirm or edit the result before it becomes part of the wardrobe. The current product centers on wardrobe organization and AI-assisted item entry, with outfit recommendations planned as a future capability.

## Architecture Overview

```text
Frontend (React / Vite on Vercel)
        |
        v
FastAPI Backend (Render)
  - REST API
  - upload finalization
  - durable AI job queue
        |
        v
AI Worker Service (Render)
  - queue polling loop
  - minimal /health endpoint
        |
        v
Supabase
  |- Postgres
  |- Auth
  `- Storage
```

```text
User uploads image
        |
        v
POST /items/presign
        |
        v
Direct upload to Supabase Storage
        |
        v
POST /items/{id}/complete-upload
        |
        v
Image variants created + ai_jobs row queued
        |
        v
Worker service runs AI pipeline
        |
        v
Predictions stored in Postgres
        |
        v
Frontend review screen confirms or edits results
```

## Key Features

- Upload clothing images into a personal wardrobe
- Automatically classify category and subcategory
- Detect dominant item colors
- Generate AI-assisted tags and review suggestions
- Organize items in a searchable wardrobe UI
- Process AI jobs through a durable queue
- Review, correct, and save predictions before finalizing

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| Infrastructure | Vercel, Render, Supabase |
| AI / Computer Vision | OpenCLIP embeddings, Pillow, NumPy, scikit-learn color clustering, optional OpenCV masking |

## Project Structure

<!-- project-structure:start -->
```text
apps/
  web/         React frontend for wardrobe, upload, and review flows

services/
  api/         FastAPI API, AI worker service, database models, and migrations

docs/
  architecture/ deployment and worker design notes
  config/       environment and platform configuration docs
  process/      delivery workflow notes

.github/
  workflows/    GitHub Actions CI and deployment verification

scripts/
  ci/           docs sync, security gating, and startup verification helpers

dev.sh         One-command local launcher for web, API, worker, DB, and migrations
render.yaml    Render service definitions for the API and AI worker
Makefile       Repo-level convenience commands
```
<!-- project-structure:end -->

## Local Development

### Quick Start

```bash
./dev.sh
# or
make dev
```

This starts local Postgres in Docker, runs migrations, creates missing env files from the checked-in examples, launches the API on `http://127.0.0.1:8000`, launches the worker service on `http://127.0.0.1:8001/health`, and launches the web app on `http://127.0.0.1:5173`.

Useful checks:

```bash
make lint
make test
make typecheck
```

### Run Services Individually

Frontend:

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Backend:

```bash
cd services/api
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
make db-up
make upgrade
make run
make worker-service
```

AI processing:

```bash
cd services/api
make worker-service

# standalone worker entrypoint for debugging
make worker
```

Real auth and live uploads require Supabase values in `apps/web/.env.local` and `services/api/.env`. Without them, local guest mode still works with the API's local auth bypass path.

<!-- ci-cd:start -->
## CI/CD Pipeline

- `.github/workflows/ci.yml` runs on every pull request and branch push.
- Backend validation runs `python -m ruff check .`, `python -m mypy app`, `python -m pytest -q`, and `python scripts/ci/verify_backend.py` against PostgreSQL.
- Frontend validation runs `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`.
- Security checks run `actions/dependency-review-action`, `npm audit --audit-level=high`, `pip-audit`, and `gitleaks`.
- `python scripts/ci/sync_docs.py --check` fails when the generated documentation sections drift from the current repo shape.
- After merge to `main`, `.github/workflows/deploy.yml` waits for the platform Git deploy window and polls `DEPLOY_HEALTHCHECK_URL` (defaults to `https://styleus-api.onrender.com/health`) until `/health` reports `status=ok` and `database=ok`.
<!-- ci-cd:end -->

## AI Pipeline

```text
image upload
  -> source image stored in Supabase Storage
  -> upload finalized by FastAPI
  -> image variants generated
  -> AI job queued in Postgres
  -> classification + color extraction + tag generation
  -> predictions saved to the database
  -> frontend review screen loads the preview
```

The API does not import the heavy AI runtime at boot. On the free-tier default config, `AI_ENABLE_CLASSIFIER=false` makes upload completion run the lightweight heuristic pipeline inline in the API, which measured about `288 MB` RSS and `1.4s` on a sample image. Full CLIP inference remains available only when `AI_ENABLE_CLASSIFIER=true` and a higher-memory worker service is deployed.

## Deployment Overview

- Frontend -> Vercel (`apps/web`)
- API -> Render web service (`services/api`, `Dockerfile`)
- AI worker -> Render web service (`services/api`, `Dockerfile.worker`)
- Database / Auth / Storage -> Supabase

Deployment config in this repo:

- [apps/web/vercel.json](apps/web/vercel.json)
- [render.yaml](render.yaml)

## Further Reading

- [apps/web/README.md](apps/web/README.md)
- [services/api/README.md](services/api/README.md)
- [docs/architecture/deployment.md](docs/architecture/deployment.md)
- [docs/config/environments.md](docs/config/environments.md)
