# Repository Guidelines

## 1. Repository overview

StyleUs is an AI-assisted wardrobe platform. The core user flow is: upload a clothing photo, run AI classification and color/tag extraction, review the result, save the item into the wardrobe, and later use that structured data for similarity search and outfit recommendations.

The current business goal is reliable wardrobe ingestion: reduce manual data entry while keeping category predictions trustworthy enough that users will accept or lightly edit AI output instead of redoing it by hand.

## 2. Architecture map

- `apps/web`: Vite + React frontend. Main routes live in `apps/web/src/pages`; upload review is `apps/web/src/pages/UploadReviewPage.tsx`; API access is centralized in `apps/web/src/lib/api.ts`.
- `services/api`: FastAPI API. Entry point is `services/api/app/main.py`; HTTP routes live in `services/api/app/api/routers`; business logic lives in `services/api/app/services`.
- `services/api/app/ai` and `services/api/app/worker_service.py`: AI pipeline, queue worker, and worker web service.
- Supabase: shared Postgres, browser auth, and private object storage.
- Deployment: Vercel serves `apps/web`; Render runs `services/api/Dockerfile` for the API and `services/api/Dockerfile.worker` for the AI worker; `render.yaml` captures the hosted shape.
- CI/CD: `.github/workflows/ci.yml` validates pushes and PRs; `.github/workflows/deploy.yml` verifies production after merges to `main`.

## 3. Service boundaries

- Frontend owns browser auth, upload UX, polling, review/edit flows, and presentation state only.
- API owns token validation, presigned uploads, upload finalization, image variant creation, CRUD, authorization, and any write that affects wardrobe truth.
- Worker owns `ai_jobs` claiming, retry/stale recovery, preprocessing, segmentation, CLIP inference, embeddings, and preview payload persistence.
- Supabase owns Postgres rows, Auth sessions, and private Storage objects.
- Never move into client-side logic: `DATABASE_URL`, service-role keys, auth enforcement, queue semantics, upload finalization, AI thresholds, or business rules.

## 4. Local development workflow

```bash
# full stack
./dev.sh
# or
make dev

# repo-level checks
make lint
make test
make typecheck
python scripts/ci/sync_docs.py --check
python scripts/ci/verify_backend.py
```

```bash
# frontend
cd apps/web
npm install
cp .env.example .env.local
npm run dev
npm run build
npm run lint
npm run typecheck
npm test
```

```bash
# backend + worker
cd services/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make db-up
make upgrade
make run
make worker-service
make worker
make migrate MESSAGE=add_new_field
```

## 5. Deployment workflow

- Vercel deploys `apps/web` through Git integration using `apps/web/vercel.json`.
- Render deploys the API from `services/api/Dockerfile`; `render.yaml` sets `preDeployCommand: python -m alembic upgrade head` and health checks `/health`.
- Render deploys the worker from `services/api/Dockerfile.worker`; it serves `uvicorn app.worker_service:app`.
- Hosted services share Supabase and should remain compatible with `RUN_MIGRATIONS_ON_START=true`.
- After merges to `main`, GitHub Actions waits for Git-triggered deploys and polls the API health endpoint, plus the frontend URL when configured.

## 6. Database + migration rules

- Alembic in `services/api/alembic` is the only schema source of truth.
- Schema changes must update SQLAlchemy models, API schemas, and an Alembic revision together.
- Create revisions with `cd services/api && make migrate MESSAGE=...`, review the generated migration, then apply with `make upgrade`.
- Do not patch schema through the Supabase dashboard without a committed migration.
- Do not disable startup migration checks or tolerate drift between API, worker, and database.
- Current production shape includes `202603181030_add_ai_embeddings_and_attributes.py`; preserve compatibility with existing AI columns.

## 7. AI system rules

- Core pipeline files: `services/api/app/ai/pipeline.py`, `clip_heads.py`, `segmentation.py`, `color.py`, `tasks.py`, and `worker.py`.
- Default free-tier mode keeps uploads usable with inline heuristic enrichment when `AI_ENABLE_CLASSIFIER=false`.
- Full classifier mode uses durable `ai_jobs` rows with `pending`, `running`, `completed`, and `failed` states plus `SELECT ... FOR UPDATE SKIP LOCKED`.
- FashionCLIP/OpenCLIP inference produces category, subcategory, colors, tags, and embeddings; preview data is returned by `GET /items/{id}/ai-preview`.
- Confidence gates come from `AI_CONFIDENCE_THRESHOLD`, `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`, and `AI_TAG_CONFIDENCE_THRESHOLD`. Tune them; do not bypass them.
- The current blocker is AI prediction quality regression, especially category quality, plus uncertainty UI noise. Fix prediction quality and segmentation crop quality before adding new AI surface area.

## 8. Frontend UX rules

- Keep the web app premium, modern, and fashion-tech; avoid noisy utility styling.
- The review screen is a trust surface. Favor clear imagery, clean hierarchy, and subtle confidence communication.
- Category accuracy matters more than decorative UI.
- Uncertainty should stay understated: one review banner and light field emphasis, not repeated badges or alarm-heavy UI.
- Preserve the clean product feel in `apps/web/src/pages` and `apps/web/src/components`.

## 9. CI/CD rules

- Keep `.github/workflows/ci.yml` green: workflow validation, docs sync, backend lint/type/tests/startup verification, frontend lint/type/tests/build, and security checks.
- Do not weaken `npm audit`, `pip-audit`, dependency review, `gitleaks`, or secret-scanning review.
- CI must stay self-contained. Do not require live Vercel, Render, or Supabase services for tests.
- Backend CI uses sqlite and mocked storage; frontend CI uses mock-friendly env flags and tests.

## 10. Guardrails for AI agents

- Prefer targeted regression fixes over broad rewrites.
- Do not redesign the Vercel + Render + Supabase split casually.
- Do not weaken auth, move business logic into the frontend, or expose backend-only settings to the browser.
- Do not bypass Alembic, disable schema validation, or replace the durable queue with ad hoc background work.
- Preserve `/health`, deployment compatibility, and the current API contracts unless a coordinated migration is part of the change.

## 11. Current roadmap / next priorities

1. Restore strong category prediction quality.
2. Improve segmentation crop quality.
3. Reduce uncertainty UI noise on the review flow.
4. Tune thresholds and preview rules.
5. Revisit similarity search and outfit intelligence after ingestion quality is stable.

## 12. Code and PR hygiene

- `.editorconfig` sets UTF-8, LF, final newline, spaces, and 2-space indentation.
- Frontend formatting is Prettier-based; backend quality gates are Ruff and MyPy.
- Test naming follows `apps/web/src/**/*.test.tsx` and `services/api/tests/test_*.py`.
- Branch names use `feat/*`, `fix/*`, or `chore/*`.
- Commits should follow Conventional Commits, for example `fix(ai): tighten preview threshold`.
- PRs should stay focused, reference the related issue or ADR, include UI screenshots when the review flow changes, and merge only with approval plus green CI.

## Agent Operating Model

This repository is designed to be worked on by one primary reasoning model and multiple focused execution agents.

### Primary Brain
The primary model is the architectural brain of the project.
Its responsibilities are:
- understand the full repository
- maintain the global roadmap
- reason about tradeoffs
- decide priorities
- detect regressions
- define implementation plans
- review worker outputs for consistency

The primary brain should prefer deep reasoning before implementation.
It should break work into focused tasks and delegate them when useful.

### Worker Agents
Worker agents are execution-focused.
They may be used for:
- implementing isolated backend changes
- fixing CI/CD
- refactoring frontend screens
- improving AI pipeline components
- updating docs
- writing migrations
- stabilizing tests

Worker agents should not make architecture decisions independently unless explicitly instructed.
They should solve the scoped task they are assigned and report back clearly.

### Delegation Rule
Use the primary brain for:
- repository-wide reasoning
- architecture changes
- roadmap decisions
- debugging complex regressions
- deciding between alternative approaches

Use worker agents for:
- bounded implementation tasks
- repetitive cleanup
- documentation updates
- targeted bug fixes
- CI/test repairs

### Review Rule
All worker outputs should be reviewed through the primary brain before being treated as the project direction.
The primary brain is responsible for keeping:
- architecture coherent
- deployment safe
- AI quality measurable
- UX aligned with product goals

### Current Preferred Workflow
1. Primary brain analyzes the goal.
2. Primary brain decomposes the work.
3. Worker agents execute focused tasks.
4. Primary brain reviews results.
5. CI validates.
6. Human merges.

This repository should follow a “one brain, many workers” operating model rather than independent autonomous agents making uncoordinated changes.
