# AI Worker

The API queues enrichment work and a separate lightweight worker web service executes it. Heavy inference never runs in the request-response path or inside the main API process.

## Flow

1. `POST /items/{item_id}/complete-upload` finalizes image variants and inserts or reuses one `ai_jobs` row.
2. The worker web service starts `app/ai/worker.py` in a background thread, warms the pipeline once, and continuously polls for claimable jobs.
3. The worker claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED`.
4. The worker downloads the normalized image, runs the AI pipeline, updates the item, and stores the preview payload on the job.
5. `GET /items/{item_id}/ai-preview` returns persisted predictions and the current job state.

## Queue behavior

- one durable job per item
- statuses: `pending`, `running`, `completed`, `failed`
- each claim increments `attempts`
- failures retry until `AI_JOB_MAX_ATTEMPTS`
- stale `running` jobs become claimable again after `AI_JOB_STALE_AFTER_SECONDS`

This makes the worker restart-safe without changing the user-visible API while keeping the inference memory footprint out of the API service.

## Logs to watch

- `worker.warmup_started`
- `worker.job_claimed`
- `ai.tasks.image_fetch_started`
- `ai.tasks.image_fetched`
- `ai.pipeline.timings`
- `worker.job_completed`
- `worker.job_failed`
- `memory_rss_mb`

## Local run

```bash
cd services/api
make worker-service
```

The standalone `python -m app.worker` entrypoint remains available for one-off debugging, but Render deploys the worker through `uvicorn app.worker_service:app`.

## Render deployment

The hosted backend now runs as two Render web services that share the same codebase and database.

- Root Directory: `services/api`
- Runtime: `Docker`
- API Start Command: Docker default from `services/api/Dockerfile`
- Worker Start Command: `uvicorn app.worker_service:app --host 0.0.0.0 --port ${PORT}`
- Shared env vars: `APP_ENV`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `AI_ENABLE_CLASSIFIER`, `AI_JOB_POLL_INTERVAL_SECONDS`, `AI_JOB_MAX_ATTEMPTS`, `AI_JOB_STALE_AFTER_SECONDS`

The repository-level [../../render.yaml](../../render.yaml) file captures this two-service definition.
