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

## Color pipeline audit (background leakage)
- Color extraction lives in `services/api/app/ai/color.py`: loads the image, center-crops to a square, resizes to 256×256, flattens all pixels, converts to LAB, then runs KMeans to map cluster centers to a fixed palette.
- No masking/segmentation is applied—every pixel in the center crop is used—so backgrounds that occupy the crop dominate the histogram and influence primary/secondary colors.
- There is no other background suppression elsewhere in the pipeline; `pipeline.run` simply calls `color.get_colors` on the raw file.

## Background suppression changes
- Added `app/ai/segmentation.py` with GrabCut (when OpenCV is present) and heuristic masking plus largest-component/edge smoothing helpers; `get_colors` now applies the mask before LAB/KMeans and falls back to the prior center-crop path when masking fails or is too small.
- New knobs: `AI_COLOR_USE_MASK` (default true), `AI_COLOR_MASK_METHOD` (`grabcut`/`heuristic`), `AI_COLOR_MIN_FOREGROUND_PIXELS` (3000 default). Tests now generate synthetic garments to assert masked colors ignore backgrounds.
- Added `opencv-python-headless` to backend deps so GrabCut is available when running `make dev`/`make setup`.
