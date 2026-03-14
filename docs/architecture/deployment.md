# Deployment Architecture

StyleUs deploys as four pieces:

- frontend on Vercel
- API on a Render web service
- AI worker on a separate lightweight Render web service
- Postgres, Auth, and Storage on Supabase

## Runtime boundaries

Vercel frontend:

- serves the Vite build from `apps/web/dist`
- runs the browser-only auth client
- uploads source images directly to Supabase Storage using signed upload tokens from the API
- calls the Render API through `VITE_API_BASE_URL`

Render API:

- runs FastAPI from `services/api`
- builds from `services/api/Dockerfile`, which installs only the base backend dependencies
- should use Render `starter` if you want a non-sleeping production API; the process itself stays within a 512 MB budget
- validates Supabase bearer tokens
- creates presigned upload intents
- finalizes uploads into private Storage paths
- writes wardrobe items and AI jobs to Supabase Postgres
- exposes `/health` for Render health checks

Render AI worker:

- builds from `services/api/Dockerfile.worker`, which installs the `.[ai]` extra
- should use Render `standard` or higher because the current CLIP warmup reaches about `1489 MB` RSS locally
- runs `uvicorn app.worker_service:app`
- starts the reusable `app/ai/worker.py` loop at startup
- loads and warms the model state lazily on the first claimed job, then reuses it across jobs
- reads and updates the shared `ai_jobs` table for asynchronous enrichment work
- exposes `/health` for Render health checks
- idles around `110 MB` RSS locally, but the current CLIP warmup reaches about `1489 MB` RSS, so it should not be placed on a 512 MB Render instance

Supabase:

- stores the Postgres database used by SQLAlchemy and Alembic
- issues browser sessions and access tokens through Supabase Auth
- stores original uploads plus `orig.jpg`, `medium.jpg`, and `thumb.jpg` variants in private Storage

## Request flow

1. The user authenticates in the Vercel-hosted frontend through Supabase Auth.
2. The frontend calls `POST /items/presign` on the Render API.
3. The API creates the placeholder row and returns a signed upload target.
4. The browser uploads the image directly to Supabase Storage.
5. The frontend calls `POST /items/{item_id}/complete-upload`.
6. The API validates the uploaded source image, writes derived variants, and enqueues an `ai_jobs` row.
7. The worker service polls the queue, processes the item, and stores predictions.
8. The frontend polls `GET /items/{item_id}/ai-preview` until the review screen can show the result.

## Deployment files in this repo

- `apps/web/vercel.json` - Vercel build output and SPA rewrites
- `render.yaml` - Render web service blueprint
- `services/api/Dockerfile` - API image without AI inference extras
- `services/api/Dockerfile.worker` - worker image with AI inference extras
- `apps/web/.env.example` - frontend local env template using the hosted variable names
- `services/api/.env.example` - backend local env template using the hosted variable names

## Boundary rules

The frontend may know:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_APP_ENV`

The frontend must not know:

- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- any Alembic or AI job settings

The API owns:

- client-facing CRUD and auth enforcement
- presigned upload creation and upload finalization
- writes that create wardrobe rows and enqueue AI jobs

The worker owns:

- claiming queued AI jobs
- running enrichment and retry logic
- writing AI predictions back to the database

Both backend services own:

- private database access
- private Storage operations
- service-role credentials

<!-- ci-cd:start -->
## CI/CD Pipeline

- Pull requests and branch pushes run `.github/workflows/ci.yml`.
- GitHub Actions validates backend linting, type checking, tests, startup verification, frontend checks, documentation sync, dependency review, `npm audit`, `pip-audit`, and `gitleaks`.
- Merges to `main` let Vercel and Render deploy through Git integration; `.github/workflows/deploy.yml` only verifies the result by polling `DEPLOY_HEALTHCHECK_URL` (defaults to `https://styleus-api.onrender.com/health`).
- The production readiness gate is `GET /health`, which must confirm both API liveness and database connectivity.
<!-- ci-cd:end -->
