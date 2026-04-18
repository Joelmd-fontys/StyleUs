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
- builds from `services/api/Dockerfile`, which installs the base runtime dependencies including `numpy` and `scikit-learn`
- queues classifier-backed enrichment in the intended production path
- measured locally at about `288 MB` RSS and `1.4s` for a sample heuristic enrichment run
- validates Supabase bearer tokens
- creates presigned upload intents
- finalizes uploads into private Storage paths
- writes wardrobe items to Supabase Postgres and, in free-tier mode, computes heuristic suggestions inline
- exposes `/health` for Render health checks

Render AI worker:

- builds from `services/api/Dockerfile.worker`, which installs the base runtime plus the `.[ai]` extra
- is required in the intended production deployment
- runs with `AI_ENABLE_CLASSIFIER=true`
- needs a higher-memory instance because the current `ViT-B-32` warmup reaches about `1600 MB` RSS locally
- runs `uvicorn app.worker_service:app`
- starts the reusable `app/ai/worker.py` loop at startup
- loads and warms the model state lazily on the first claimed job, then reuses it across jobs
- reads and updates the shared `ai_jobs` table for asynchronous enrichment work
- exposes `/health` for Render health checks
- reports `mode=disabled` on `/health` when `AI_ENABLE_CLASSIFIER=false`

## Schema migrations

- Alembic is the schema source of truth for the API and worker.
- The current production head includes `202603181030_add_ai_embeddings_and_attributes.py`, which adds `wardrobe_items.ai_attribute_tags`, `wardrobe_items.ai_embedding`, and `wardrobe_items.ai_embedding_model`.
- If a hosted deployment reports those columns as missing, run `cd services/api && python -m alembic upgrade head` against the production `DATABASE_URL` before restarting services.

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

- Pull requests run local-safe validation only; deployment
  happens through Vercel and Render after merge.
- `.github/workflows/deploy.yml` verifies the hosted API at
  `/health`, the worker `/health` endpoint, and the
  optional frontend URL after the platform deploy window.
- The canonical delivery workflow and CI/CD operating notes
  live in `docs/process/workflow.md`.
<!-- ci-cd:end -->
