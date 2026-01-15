# StyleUs API Service

FastAPI backend for StyleUs wardrobe management. It handles presigned uploads (S3 or local), persists wardrobe items in PostgreSQL, and enriches uploads with a local-first AI pipeline.

## Requirements
- Python 3.11
- Docker (for local PostgreSQL)
- AWS credentials only if you want S3 uploads; local uploads work without them.

## Environment variables
Copy `.env.example` to `.env` and adjust as needed.

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `local`, `staging`, or `production` | `local` |
| `APP_VERSION` | Reported by `/health` and `/version` | `0.1.0` |
| `API_KEY` | Required in staging/production for `X-API-Key` auth | _(unset)_ |
| `DATABASE_URL` | SQLAlchemy connection string | _(required)_ |
| `CORS_ORIGINS` | CSV of allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `UPLOAD_MODE` | `s3` or `local`; auto-detected from AWS vars | auto |
| `MEDIA_ROOT` | Directory for local uploads | `./media` |
| `MEDIA_URL_PATH` | Public URL prefix for local media | `/media` |
| `MEDIA_MAX_UPLOAD_SIZE` | Max upload size (bytes) | `15728640` |
| `AWS_REGION` / `S3_BUCKET_NAME` | Required when using S3 uploads | _(unset)_ |
| `AI_ENABLE_CLASSIFIER` | Toggle background classification | `true` |
| `AI_DEVICE` | Torch device string (`cpu`/`cuda`) | `cpu` |
| `AI_CONFIDENCE_THRESHOLD` | Minimum confidence for writes | `0.6` |
| `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD` | Subcategory confidence floor | `0.5` |
| `AI_COLOR_TOPK` | Number of colors to keep | `2` |
| `AI_ONNX` / `AI_ONNX_MODEL_PATH` | Enable ONNX CLIP encoder | `false` / _(unset)_ |
| `SEED_ON_START` / `SEED_LIMIT` / `SEED_KEY` | Local seeding controls | `true` / `25` / `local-seed-v1` |

Local media lives under `MEDIA_ROOT` (gitignored) and is served at `MEDIA_URL_PATH`.

## Local development
```bash
cp .env.example .env
make setup
make db-up
alembic upgrade head     # or rely on startup auto-migration
make run                 # http://127.0.0.1:8000
```
Stop Postgres with `make db-down`. Use `make seed` to populate the local wardrobe or `make reset-seed` to clear it.

## Docker Compose
From `services/api`:
```bash
docker compose up --build
```
The API is exposed on `http://localhost:8000` with a persistent `styleus-pgdata` volume. Override env vars inline (e.g., `AWS_REGION=us-west-2 docker compose up`).

## Upload modes
- **Local (default without AWS vars):** `/items/presign` returns an API upload sink; files are stored under `MEDIA_ROOT/<item_id>/` and served from `MEDIA_URL_PATH`.
- **S3:** When `AWS_REGION` and `S3_BUCKET_NAME` are set, `/items/presign` returns presigned S3 URLs; final URLs are built from the bucket/region unless the client supplies one.

Every upload writes image metadata (dimensions, bytes, mime type, checksum) and generates `imageUrl`, `mediumUrl`, and `thumbUrl`.

## AI classification (local-first)
A background task runs after upload completion:
- Prefers a local CLIP model (`open-clip-torch`, optional ONNX) for category/subcategory/material/style tags.
- Falls back to deterministic color + keyword heuristics if CLIP is unavailable.
- Embeddings are cached under `MEDIA_ROOT/.emb_cache/`.
- Controlled via `AI_ENABLE_CLASSIFIER`, `AI_DEVICE`, `AI_CONFIDENCE_THRESHOLD`, and `AI_SUBCATEGORY_CONFIDENCE_THRESHOLD`.

## Testing & quality
- `make lint` – Ruff
- `make typecheck` – mypy
- `make test` – pytest (SQLite with mocked AWS)
- `make migrate MESSAGE="short description"` – create an Alembic revision
- `make upgrade` – apply migrations

## Troubleshooting
- **Port 5432 in use:** change the mapping in `docker-compose.yml` (e.g., `5433:5432`) and update `DATABASE_URL`.
- **Migrations failing:** ensure `make db-up` ran, then `alembic upgrade head`; if the volume is corrupt, remove `styleus-db` and `styleus-pgdata`.
- **Local media cleanup:** delete paths under `MEDIA_ROOT` if your disk fills; they are safe to regenerate from new uploads or seeds.
