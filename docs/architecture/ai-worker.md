# AI Worker

The API can run in two modes:

- free-tier default: heuristic enrichment runs inline during upload completion and the worker can stay disabled
- full classifier mode: a separate lightweight worker web service executes queued CLIP inference jobs

## Flow

1. `POST /items/{item_id}/complete-upload` finalizes image variants.
2. When `AI_ENABLE_CLASSIFIER=false`, the API runs the heuristic pipeline inline and returns with no queued job.
3. When `AI_ENABLE_CLASSIFIER=true`, the API inserts or reuses one `ai_jobs` row.
4. The worker web service starts `app/ai/worker.py` in a background thread and warms the pipeline once before it begins polling for jobs.
5. The worker claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED`.
6. The worker downloads the normalized image, runs garment-focused preprocessing, predicts structured labels and colors, stores an embedding on the item, and writes the full preview payload on the job.
7. `GET /items/{item_id}/ai-preview` returns persisted predictions and the current job state.

## Queue behavior

- one durable job per item
- statuses: `pending`, `running`, `completed`, `failed`
- each claim increments `attempts`
- failures retry until `AI_JOB_MAX_ATTEMPTS`
- stale `running` jobs become claimable again after `AI_JOB_STALE_AFTER_SECONDS`

This keeps the free-tier path usable without changing the upload UI while still preserving the queue-based worker path for higher-memory deployments.

## Logs to watch

- `worker.warmup_started`
- `worker.job_claimed`
- `ai.tasks.image_fetch_started`
- `ai.tasks.image_fetched`
- `ai.pipeline.preprocessing`
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
- Worker Start Command: Docker default from `services/api/Dockerfile.worker`
- Shared env vars: `APP_ENV`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `AI_ENABLE_CLASSIFIER`, `AI_JOB_POLL_INTERVAL_SECONDS`, `AI_JOB_MAX_ATTEMPTS`, `AI_JOB_STALE_AFTER_SECONDS`
- Additional AI tuning vars: `AI_MODEL_NAME`, `AI_MODEL_PRETRAINED`, `AI_MODEL_CACHE_DIR`, `AI_TAG_CONFIDENCE_THRESHOLD`

The repository-level [../../render.yaml](../../render.yaml) file captures this two-service definition.

## Memory notes

- `app.main` no longer imports the AI runtime at API boot.
- The free-tier default uses inline heuristics and avoids loading CLIP entirely.
- The worker only imports and warms the inference pipeline when it has a job to process.
- The worker Docker image caps BLAS and Torch thread pools to reduce idle overhead on Render.
- Measured locally, the heuristic API path is about `288 MB` RSS and `1.4s` on a sample image.
- Measured locally, worker idle `/health` is about `110 MB` RSS while the current PyTorch/OpenCLIP warmup reaches about `1489 MB` RSS.
- Result: free-tier deployments should leave `AI_ENABLE_CLASSIFIER=false`.
