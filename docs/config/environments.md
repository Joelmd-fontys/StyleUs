# Environment Model

StyleUs uses three runtime tiers:

| Environment | Frontend | Backend | Defaults |
| --- | --- | --- | --- |
| `local` | Vite dev server | FastAPI on the developer machine | migrations `on`, seed `on` |
| `staging` | Vercel preview or staging | Render web service | migrations `off`, seed `off` |
| `production` | Vercel production | Render web service | migrations `off`, seed `off` |

## Local files

- `apps/web/.env.example` -> `apps/web/.env.local`
- `services/api/.env.example` -> `services/api/.env`

Hosted environments should use platform-managed secrets:

- Vercel for the web app
- Render for the API and worker
- Supabase for database, auth, and storage infrastructure

## Frontend variables

These values are browser-visible:

- `VITE_APP_ENV`
- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`
- `VITE_SUPABASE_ANON_KEY` as a legacy alias
- `VITE_USE_LIVE_API_ITEMS`
- `VITE_USE_LIVE_API_UPLOAD`

Rules:

- the `VITE_USE_LIVE_API_*` flags are local-development toggles
- if `VITE_SUPABASE_URL` and a public browser key are missing, the frontend falls back to local guest mode
- hosted environments should always provide the public Supabase values

## Backend variables

Core:

- `APP_ENV`
- `APP_VERSION`
- `DATABASE_URL`
- `CORS_ORIGINS`

Auth and storage:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY` only for legacy shared-secret verification
- `LOCAL_AUTH_BYPASS`, `LOCAL_AUTH_USER_ID`, `LOCAL_AUTH_EMAIL` for local-only bypass mode

Media, startup, and worker:

- `MEDIA_ROOT`
- `MEDIA_MAX_UPLOAD_SIZE`
- `SUPABASE_SIGNED_URL_TTL_SECONDS`
- `SUPABASE_HTTP_TIMEOUT_SECONDS`
- `RUN_MIGRATIONS_ON_START`
- `RUN_SEED_ON_START`
- `AI_ENABLE_CLASSIFIER`
- `AI_DEVICE`
- `AI_CONFIDENCE_THRESHOLD`
- `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`
- `AI_COLOR_USE_MASK`
- `AI_COLOR_MASK_METHOD`
- `AI_COLOR_MIN_FOREGROUND_PIXELS`
- `AI_COLOR_TOPK`
- `AI_ONNX`
- `AI_ONNX_MODEL_PATH`
- `AI_JOB_MAX_ATTEMPTS`
- `AI_JOB_POLL_INTERVAL_SECONDS`
- `AI_JOB_STALE_AFTER_SECONDS`
- `SEED_LIMIT`
- `SEED_KEY`

Rules:

- `APP_ENV` is required
- `LOCAL_AUTH_BYPASS` is valid only when `APP_ENV=local`
- `staging` and `production` require `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`
- `RUN_MIGRATIONS_ON_START` and `RUN_SEED_ON_START` default to `true` only in `local`
- `SEED_ON_START` is still accepted as a legacy alias for `RUN_SEED_ON_START`

## Database rule

`DATABASE_URL` is the only database setting. The backend continues to use SQLAlchemy and Alembic in every environment.

- `local` typically points to Docker Postgres
- `staging` and `production` can point to Supabase Postgres
- `postgres://` and `postgresql://` URLs are normalized to the psycopg SQLAlchemy dialect
- hosted connections should keep `sslmode=require`

Alembic remains the only schema migration path.
