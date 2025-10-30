# Recap

## What We Already Have
- **Frontend**: Vite + React 18 + TypeScript app with Tailwind styling, React Router pages (dashboard, wardrobe grid, item detail, placeholders) and a Zustand wardrobe store coordinating API + mock flows (`apps/web/src/pages`, `apps/web/src/store/wardrobe.ts`). UploadPanel handles presign → PUT upload → completion with live/local support (`apps/web/src/components/UploadPanel.tsx`).
- **Backend**: FastAPI service exposing `/health`, `/version`, `/items`, `/items/presign`, `/items/uploads/{id}`, and `/items/{id}/complete-upload` with SQLAlchemy models, Alembic migrations, and dual upload modes (S3 or local disk) plus API-key enforcement in secure envs (`services/api/app/api`, `services/api/app/models/wardrobe.py`, `services/api/app/services/uploads.py`).
- **Database**: PostgreSQL 16 via Docker (`styleus-db`) on `postgresql+psycopg://postgres:postgres@localhost:5432/postgres`; migrations applied and `/health` verified; all SQLite fallbacks removed; next step is optional seeding + AI enrichment once desired.
- **AI v1**: Local-first pipeline (multi-head CLIP + LAB/KMeans color detector) enriches uploads with category, subcategory, primary/secondary colors, and merged style/material tags using cached embeddings with heuristic fallback; controlled by `AI_ENABLE_CLASSIFIER` (`services/api/app/ai/`, `services/api/app/api/routers/uploads.py`).
- **Tests & CI**: Pytest suite covering presign, upload finalization (S3 + local), and seeding; `make lint` runs Ruff with modern config; frontend `npm run typecheck` is clean. GitHub workflow scaffold exists but is still a placeholder (`services/api/tests`, `apps/web/package.json`, `.github/workflows`).
- **Docs & Env**: Updated service READMEs document setup, scripts, and feature flags; new `.env.example` files guide local configuration for both web and API (`apps/web/README.md`, `services/api/README.md`, `apps/web/.env.example`, `services/api/.env.example`).

## Known Gaps / Risks
- CI workflow does not yet execute lint/typecheck/test targets, so regressions rely on manual runs.
- Frontend lacks automated tests; only manual verification enforces UI behavior and upload flows.
- Local media artefacts are still tracked in git history; future uploads are ignored but existing blobs remain until a cleanup decision is made.
- Pagination, sorting, and richer filters are absent on both API and UI, limiting scalability of larger wardrobes.
- Error and retry UX is basic—fetch/upload failures surface as single-line messages with no retry/backoff guidance.
- Auth beyond API key and multi-user session handling are not implemented; privacy boundaries rely on seeded UUID alone.
- CLIP prompts still need calibration for edge categories; currently confidence thresholding can skip helpful predictions when items are partially obstructed.

## Next Options

### Small (1–3 hours)
- Add inline error banners & retry buttons for wardrobe list/detail requests — Purpose: improve recovery hints when fetches fail; Key files: `apps/web/src/store/wardrobe.ts`, `apps/web/src/components/ItemCard.tsx`; Acceptance: user can retry failed loads without refreshing and sees contextual messaging.
- Document MSW/live flag workflows with quick troubleshooting in web README — Purpose: reduce setup confusion when switching between mocks and API; Key files: `apps/web/README.md`; Acceptance: README includes flag explanations, troubleshooting (service worker cache, restarting dev server), and expected outcomes.
- Script media cleanup for tests — Purpose: ensure local uploads directory is purged between runs to avoid bloating the repo; Key files: `services/api/tests/conftest.py`, `services/api/Makefile`; Acceptance: running tests leaves `services/api/media` empty (or restored) and docs mention cleanup command.
- Collect AI inference telemetry (confidence histograms, cache hit rate) — Purpose: tune prompt sets and thresholds; Key files: `services/api/app/ai/tasks.py`, logging config; Acceptance: structured logs capture prediction outcomes without impacting runtime.

### Medium (0.5–2 days)
- Implement pagination & sorting end-to-end — Purpose: allow scalable browsing of large wardrobes; Key files: `services/api/app/api/routers/items.py`, `services/api/app/services/items.py`, `apps/web/src/lib/api.ts`, `apps/web/src/pages/Wardrobe.tsx`; Acceptance: API accepts `limit/offset/sort`, UI shows pagination controls, typechecks/tests updated.
- Add thumbnail + metadata display polish in grid — Purpose: leverage medium/thumb URLs and dimensions for better presentation; Key files: `apps/web/src/components/ItemCard.tsx`, `apps/web/src/lib/media.ts`; Acceptance: grid uses thumb variants with dimension badges, shimmering placeholders, and passes typecheck.
- Expand backend logging & tracing — Purpose: correlate requests/uploads with structured logs; Key files: `services/api/app/core/logging.py`, middleware in `services/api/app/main.py`; Acceptance: request logs include latency, status, user ID, upload metrics with consistent keys.
- Train/prompt-tune CLIP label sets with curated wardrobe examples — Purpose: improve accuracy for niche garments and reduce “unknown” outcomes; Key files: `services/api/app/ai/clip_heads.py`, new fixtures; Acceptance: evaluation script shows higher confidence for long-tail labels, tests updated with calibrated thresholds.

### Larger (multi-day)
- Introduce wardrobe analytics dashboard — Purpose: give admins insight into item counts, categories, storage usage; Key files: new API routes (`services/api/app/api/routers`), aggregated queries (`services/api/app/services`), new React page (`apps/web/src/pages`); Acceptance: dashboard summarizes key metrics with real data and respects feature flags.
- Launch active-learning loop for AI pipeline — Purpose: surface low-confidence predictions to humans, collect corrections, and retrain prompts/weights; Key files: `services/api/app/ai/pipeline.py`, feedback endpoints, admin UI; Acceptance: background job ingests corrections and improves future predictions.
- External ingestion connectors (Shopify/Gmail receipts) — Purpose: ingest wardrobe items from external sources; Key files: new backend services & cron scripts (`services/api/app/services`), OAuth or webhook integration, UI import wizard; Acceptance: users can connect a source, import items, and see them in wardrobe without manual upload.

## Deferred TODOs
- Leave historical media assets checked into `services/api/media/` for now; removing them requires coordination to avoid breaking seeded demos.
- CI workflow still placeholder; replacing it needs agreement on required checks and runtime environments.
