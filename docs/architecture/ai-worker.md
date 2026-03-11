# AI Worker Architecture

Phase 5 moves AI enrichment out of the FastAPI request lifecycle and into a dedicated worker process backed by Postgres.

## Flow

```text
Frontend
-> FastAPI API
-> Supabase Postgres (items + ai_jobs)
<- AI worker polling ai_jobs
```

1. The frontend uploads media and calls `POST /items/{item_id}/complete-upload`.
2. The API finalizes image variants, persists item metadata, and inserts or reuses an `ai_jobs` row.
3. The worker polls Postgres for claimable jobs.
4. The worker claims one row with `SELECT ... FOR UPDATE SKIP LOCKED`.
5. The worker preloads shared model state once, downloads the normalized inference image, and runs the existing AI pipeline.
6. The worker updates the wardrobe item and marks the job `completed`, or requeues / fails it.

## Job table

`ai_jobs` currently stores one durable enrichment job per item:

- `id`
- `item_id`
- `status`
- `created_at`
- `started_at`
- `completed_at`
- `attempts`
- `error_message`

Statuses:

- `pending`
- `running`
- `completed`
- `failed`

## Retry and restart behavior

- Each claim increments `attempts`.
- Failures are requeued until `AI_JOB_MAX_ATTEMPTS` is reached.
- Once the retry budget is exhausted, the worker marks the row `failed`.
- `running` rows older than `AI_JOB_STALE_AFTER_SECONDS` are claimable again, which makes the worker restart-safe after crashes or forced restarts.
- Item writes remain idempotent because enrichment only fills empty or placeholder-like fields and merges tags conservatively.
- Worker logs include claim latency, image fetch, preprocessing, inference, DB write, and total job duration.

## Preview behavior

`GET /items/{item_id}/ai-preview` no longer runs synchronous inference. It returns:

- persisted AI fields already written to the item
- `pending: true|false`
- the current job metadata

The frontend can poll this endpoint until the worker finishes.

## Local runtime

Run the API and worker separately:

```bash
make run
make worker
```

Or from `services/api`:

```bash
make run
make worker
```
