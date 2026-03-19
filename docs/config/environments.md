# Environment Model

StyleUs uses three application environments:

| Environment | Frontend | Backend | Defaults |
| --- | --- | --- | --- |
| `local` | Vite dev server | FastAPI on the developer machine | migrations `on`, seed `on`, local auth bypass allowed |
| `staging` | Vercel preview or staging domain | Render web services running FastAPI plus the AI worker | migrations `off`, seed `off` |
| `production` | Vercel production domain | Render web services running FastAPI plus the AI worker | migrations `off`, seed `off` |

Hosted deployments should keep secrets in platform-managed env settings:

- Vercel for browser-visible `VITE_*` values
- Render for API and worker values
- Supabase for the actual database, auth, and storage infrastructure

## Frontend variables

These values belong in Vercel and are visible to the browser:

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | yes | Public base URL of the Render API |
| `VITE_SUPABASE_URL` | yes | Public Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | yes | Public browser key used by Supabase Auth and signed uploads |
| `VITE_APP_ENV` | yes | `local`, `staging`, or `production` |
| `VITE_USE_LIVE_API_ITEMS` | local only | MSW toggle for wardrobe routes |
| `VITE_USE_LIVE_API_UPLOAD` | local only | MSW toggle for upload routes |

Notes:

- `VITE_SUPABASE_PUBLISHABLE_KEY` remains accepted as a legacy alias, but new deployments should use `VITE_SUPABASE_ANON_KEY`.
- In `local`, the app falls back to `http://127.0.0.1:8000` if `VITE_API_BASE_URL` is unset.
- Hosted environments should not rely on local mock flags.

## Backend variables

These values belong in Render on the API and worker services.

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_ENV` | yes | Set to `production` on hosted deployments |
| `DATABASE_URL` | yes | Supabase Postgres connection string with `sslmode=require` |
| `SUPABASE_URL` | yes | Base URL for Supabase Auth and Storage |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Private key for Storage access and upload finalization |
| `SUPABASE_STORAGE_BUCKET` | yes | Private bucket used for item images |
| `CORS_ORIGINS` | yes for API | Comma-separated Vercel origins allowed to call FastAPI |
| `AI_JOB_POLL_INTERVAL_SECONDS` | yes on worker | Worker poll interval |
| `AI_JOB_MAX_ATTEMPTS` | yes on worker | Retry limit for AI jobs |
| `APP_VERSION` | optional | Returned by `/health` and `/version` |
| `AI_JOB_STALE_AFTER_SECONDS` | optional | Reclaim timeout for stuck running jobs |
| `SUPABASE_JWT_AUDIENCE` | optional | Defaults to `authenticated` |
| `SUPABASE_SIGNED_URL_TTL_SECONDS` | optional | Signed media URL lifetime |
| `SUPABASE_HTTP_TIMEOUT_SECONDS` | optional | Timeout for Supabase HTTP calls |
| `AI_ENABLE_CLASSIFIER` | optional | `false` runs lightweight heuristic enrichment inline in the API; `true` enables queued CLIP inference |
| `AI_DEVICE` | optional | Defaults to `cpu` |
| `AI_CONFIDENCE_THRESHOLD` | optional | Category threshold |
| `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD` | optional | Subcategory threshold |

Local-only backend settings:

- `LOCAL_AUTH_BYPASS`
- `LOCAL_AUTH_USER_ID`
- `LOCAL_AUTH_EMAIL`
- `RUN_MIGRATIONS_ON_START`
- `RUN_SEED_ON_START`
- `SEED_LIMIT`
- `SEED_KEY`
- `MEDIA_ROOT`
- `MEDIA_MAX_UPLOAD_SIZE`

Notes:

- `LOCAL_AUTH_BYPASS` is valid only when `APP_ENV=local`.
- `RUN_MIGRATIONS_ON_START` and `RUN_SEED_ON_START` default to `true` only in `local`.
- `SEED_ON_START` remains accepted as a legacy alias for `RUN_SEED_ON_START`.
- The hosted Render blueprint overrides `RUN_MIGRATIONS_ON_START=true` so schema migrations run before API and worker startup.
- `SUPABASE_ANON_KEY` remains accepted only for legacy shared-secret JWT verification; it is not part of the standard hosted backend contract.
- `services/api/Dockerfile` is the API image and installs the base runtime dependencies, including `numpy` and `scikit-learn`.
- `services/api/Dockerfile.worker` is the worker image and installs the same base runtime plus the `.[ai]` extra for CLIP inference and startup migrations.

## Platform mapping

Vercel:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_APP_ENV`

Render API:

- all backend required values
- `CORS_ORIGINS` must include the active Vercel origin
- `AI_ENABLE_CLASSIFIER=false` is the free-tier default
- build from `services/api/Dockerfile`

Render AI worker:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `AI_ENABLE_CLASSIFIER`
- `AI_JOB_POLL_INTERVAL_SECONDS`
- `AI_JOB_MAX_ATTEMPTS`
- `AI_JOB_STALE_AFTER_SECONDS`
- build from `services/api/Dockerfile.worker`
- keep `AI_ENABLE_CLASSIFIER=false` on free tier so the worker stays disabled and healthy
- the current PyTorch/OpenCLIP worker warmup reaches about `1489 MB` RSS locally, so only turn classifier mode back on with a higher-memory instance

Supabase:

- creates the actual Postgres URL
- provides the anon key and service role key
- hosts the Storage bucket named by `SUPABASE_STORAGE_BUCKET`

<!-- ci-cd:start -->
## CI/CD Pipeline

- CI uses local-safe values for `APP_ENV`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `LOCAL_AUTH_BYPASS`, `RUN_MIGRATIONS_ON_START`, and `RUN_SEED_ON_START`.
- Pull request validation does not require hosted platform secrets for normal backend or frontend checks.
- Deploy verification reads `DEPLOY_HEALTHCHECK_URL` (defaults to `https://styleus-api.onrender.com/health`); set the repository variable when the production API URL changes.
- Optional repository variable `DEPLOY_FRONTEND_URL` enables frontend deployment verification after backend health passes.
- Optional repository secret `SECRET_SCAN_REVIEW_GITHUB_TOKEN` enables GitHub secret-scanning alert review in CI when GitHub Advanced Security is available.
<!-- ci-cd:end -->
