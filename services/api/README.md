# StyleUs API Service

The API owns wardrobe persistence, upload finalization, local media serving, background AI enrichment, and the deterministic seed dataset used in local development.

## Stack

- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Pillow / NumPy / scikit-learn
- `open-clip-torch` with optional ONNX inference
- FastAPI `BackgroundTasks`

## Service structure

- `app/main.py` – app creation, middleware, CORS, media mount, migration-on-start, seed-on-start
- `app/api/routers` – health, version, item, and upload routes
- `app/services/items.py` – wardrobe CRUD and response shaping
- `app/services/uploads.py` – presign, local upload persistence, and upload finalization
- `app/ai` – CLIP heads, color extraction, segmentation, pipeline coordination, background task logic
- `app/models` – SQLAlchemy models
- `app/seed` – deterministic seed dataset and runner

## Main runtime flow

### Upload

1. `POST /items/presign`
2. A placeholder item is created in Postgres.
3. The client uploads bytes either:
   - to `PUT /items/uploads/{item_id}` in local mode, or
   - directly to S3 in S3 mode.
4. `POST /items/{item_id}/complete-upload`
5. The API generates `orig.jpg`, `medium.jpg`, `thumb.jpg`, stores metadata, and schedules AI classification.

### AI enrichment

The background task in `app/ai/tasks.py`:

- loads the finalized image from local media or S3;
- runs the shared pipeline in `app/ai/pipeline.py`;
- writes back colors, category, subcategory, materials, style tags, top tags, and AI confidence only when thresholds are met;
- avoids overwriting user-supplied data unless fields are still empty or placeholder-like.

### AI preview

`GET /items/{id}/ai-preview` returns a preview payload based on:

- persisted AI fields already stored on the item, plus
- a fresh non-persisted pipeline pass when the source image is available.

That endpoint is intended for the upload review UI, not as a separate persistence model.

## Routes

- `GET /health`
- `GET /version`
- `GET /items`
- `GET /items/{item_id}`
- `GET /items/{item_id}/ai-preview`
- `PATCH /items/{item_id}`
- `DELETE /items/{item_id}`
- `POST /items/presign`
- `PUT /items/uploads/{item_id}` in local upload mode
- `POST /items/{item_id}/complete-upload`

## Environment

Copy `.env.example` to `.env` before running locally.

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `local`, `staging`, `production` | `local` |
| `APP_VERSION` | value returned by `/health` and `/version` | `0.1.0` |
| `API_KEY` | enforced only in staging/production | _(unset)_ |
| `DATABASE_URL` | SQLAlchemy/Postgres connection string | required |
| `CORS_ORIGINS` | comma-separated allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `UPLOAD_MODE` | `local` or `s3`; auto-derived if omitted | auto |
| `MEDIA_ROOT` | local media directory | `./media` |
| `MEDIA_URL_PATH` | static mount path for local media | `/media` |
| `MEDIA_MAX_UPLOAD_SIZE` | upload ceiling in bytes | `15728640` |
| `AWS_REGION` / `S3_BUCKET_NAME` | required only for S3 mode | _(unset)_ |
| `AI_ENABLE_CLASSIFIER` | enable background classification | `true` |
| `AI_DEVICE` | model device, usually `cpu` locally | `cpu` |
| `AI_CONFIDENCE_THRESHOLD` | write threshold for category/material/style updates | `0.6` |
| `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD` | write threshold for subcategory updates | `0.5` |
| `AI_COLOR_USE_MASK` | enable foreground masking before color clustering | `true` |
| `AI_COLOR_MASK_METHOD` | `grabcut` or `heuristic` | `grabcut` |
| `AI_COLOR_MIN_FOREGROUND_PIXELS` | minimum masked pixel count before unmasked fallback | `3000` |
| `AI_COLOR_TOPK` | number of colors retained from clustering | `2` |
| `AI_ONNX` / `AI_ONNX_MODEL_PATH` | optional ONNX inference path | `false` / unset |
| `SEED_ON_START` / `SEED_LIMIT` / `SEED_KEY` | local seeding controls | `true` / `25` / `local-seed-v1` |

## Local development

```bash
cd services/api
cp .env.example .env
make setup
make db-up
make upgrade
make run
```

Default API URL: `http://127.0.0.1:8000`

Useful commands:

- `make seed` – apply the deterministic seed dataset
- `make reset-seed` – remove seeded items and their media
- `make lint`
- `make typecheck`
- `make test`

## Docker and Postgres

- `docker-compose.yml` starts Postgres only.
- Normal development runs the API on the host, not in Docker.
- The database container is named `styleus-db`.
- Data is persisted in the `styleus-pgdata` Docker volume.

## Testing notes

- Backend tests run with pytest.
- The current test configuration expects a Postgres database reachable via `DATABASE_URL`; the default test setup points at `postgresql+psycopg://postgres:postgres@localhost:5432/postgres`.
- AWS interactions are mocked in unit tests.

## Troubleshooting

- If `5432` is already in use, change the mapping in `docker-compose.yml` and keep `DATABASE_URL` in sync.
- If migrations fail during startup, verify Postgres is running and rerun `make upgrade`.
- Local uploads and embedding cache live under `MEDIA_ROOT`; these files are safe to delete when you want a clean media directory.
