# Deployment Architecture

StyleUs deploys as three pieces:

- frontend on Vercel
- API on a Render web service, with the AI worker loop embedded in the FastAPI process
- Postgres, Auth, and Storage on Supabase

## Runtime boundaries

Vercel frontend:

- serves the Vite build from `apps/web/dist`
- runs the browser-only auth client
- uploads source images directly to Supabase Storage using signed upload tokens from the API
- calls the Render API through `VITE_API_BASE_URL`

Render API:

- runs FastAPI from `services/api`
- starts the embedded AI worker loop during FastAPI lifespan startup
- validates Supabase bearer tokens
- creates presigned upload intents
- finalizes uploads into private Storage paths
- writes wardrobe items and AI jobs to Supabase Postgres
- reads and updates the same `ai_jobs` table for asynchronous enrichment work
- exposes `/health` for Render health checks

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
7. The API's embedded worker loop polls the queue, processes the item, and stores predictions.
8. The frontend polls `GET /items/{item_id}/ai-preview` until the review screen can show the result.

## Deployment files in this repo

- `apps/web/vercel.json` - Vercel build output and SPA rewrites
- `render.yaml` - Render web service blueprint
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

- all database access
- all private Storage operations
- all job queue state
- all service-role credentials
