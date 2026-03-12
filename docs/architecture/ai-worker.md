# AI Worker

The API queues enrichment work and the worker executes it. Heavy inference never runs in the request-response path.

## Flow

1. `POST /items/{item_id}/complete-upload` finalizes image variants and inserts or reuses one `ai_jobs` row.
2. `app/worker.py` warms the pipeline once at startup and continuously polls for claimable jobs.
3. The worker claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED`.
4. The worker downloads the normalized image, runs the AI pipeline, updates the item, and stores the preview payload on the job.
5. `GET /items/{item_id}/ai-preview` returns persisted predictions and the current job state.

## Queue behavior

- one durable job per item
- statuses: `pending`, `running`, `completed`, `failed`
- each claim increments `attempts`
- failures retry until `AI_JOB_MAX_ATTEMPTS`
- stale `running` jobs become claimable again after `AI_JOB_STALE_AFTER_SECONDS`

This makes the worker restart-safe without changing the user-visible API.

## Logs to watch

- `worker.warmup_started`
- `worker.job_claimed`
- `ai.tasks.image_fetch_started`
- `ai.tasks.image_fetched`
- `ai.pipeline.timings`
- `worker.job_completed`
- `worker.job_failed`

## Local run

```bash
cd services/api
make run
make worker
```

## Render deployment

The hosted worker runs on Render as a background worker using the same codebase and Docker image as the API.

- Root Directory: `services/api`
- Runtime: `Docker`
- Start Command: `python -m app.worker`
- Shared env vars: `APP_ENV`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `AI_JOB_POLL_INTERVAL_SECONDS`, `AI_JOB_MAX_ATTEMPTS`

The repository-level [../../render.yaml](../../render.yaml) file captures this service definition.
