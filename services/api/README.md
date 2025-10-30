# StyleUs API Service

FastAPI backend for StyleUs wardrobe management. The service uses PostgreSQL, SQLAlchemy, and Alembic with a small service layer and presigned S3 uploads.

## Requirements

- Python 3.11
- PostgreSQL 14+ (Docker recipe below)
- AWS credentials capable of generating S3 presigned URLs (mocked in tests)

### Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | `local`, `staging`, or `production` | `local` |
| `APP_VERSION` | Version string surfaced by `/health` & `/version` | `0.1.0` |
| `API_KEY` | Required in staging/production for `X-API-Key` auth | _unset_ |
| `DATABASE_URL` | SQLAlchemy connection string | _required_ |
| `AWS_REGION` | AWS region for S3 client | _required_ |
| `S3_BUCKET_NAME` | Bucket for wardrobe uploads | _required_ |
| `CORS_ORIGINS` | CSV of allowed origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `UPLOAD_MODE` | `s3` or `local`; defaults to `s3` when AWS vars present | _auto_ |
| `MEDIA_ROOT` | Directory for locally stored uploads | `./media` |
| `MEDIA_URL_PATH` | Public URL prefix for local media | `/media` |
| `MEDIA_MAX_UPLOAD_SIZE` | Max upload size in bytes | `15728640` |
| `SEED_ON_START` | Auto-run curated seed (defaults on in local env) | `true` (local) |
| `SEED_LIMIT` | Max number of seed items applied per run | `25` |
| `SEED_KEY` | Identifier stored in `seeds` table for idempotency | `local-seed-v1` |

Copy `.env.example` to `.env` for a ready-to-run local configuration.

The application fails fast in staging/production if any required variable is missing.

## Local Development

1. Start PostgreSQL (example using Docker):
   ```bash
   docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=styleus postgres:16
   ```
2. Copy `.env.example` to `.env` (or another filename) and tweak as needed. Example:
   ```env
   APP_ENV=local
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/styleus
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=styleus-dev
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   MEDIA_ROOT=./media
   MEDIA_URL_PATH=/media
   API_KEY=
   ```
3. Install dependencies:
   ```bash
   make setup
   ```
4. Launch the API (migrations run automatically on startup):
   ```bash
   make run
   ```
   If you want to apply migrations manually ahead of time, run `make upgrade`.
   Local requests bypass the `X-API-Key` guard. In staging/production, set `API_KEY` and send the header `X-API-Key: <value>` from the frontend.
   If `AWS_REGION` and `S3_BUCKET_NAME` are unset the service automatically switches to local upload mode and persists files beneath `MEDIA_ROOT`.

### One-command setup with Docker Compose

Alternatively, spin up Postgres and the API (with migrations) in one shot:

```bash
docker compose up --build
```

The compose file exposes the API on `http://localhost:8000` and persists database data in a named `pgdata` volume. Override configuration via environment variables passed to `docker compose`, e.g. `AWS_REGION=us-west-2 docker compose up`.

## Useful Commands

- `make migrate MESSAGE="short description"` – create a new Alembic revision.
- `make upgrade` – apply migrations.
- `make lint` – run Ruff.
- `make typecheck` – run mypy (targets `app/`).
- `make test` – execute pytest suite (uses SQLite + mocked AWS).
- `make seed` – populate the local wardrobe with curated starter data.
- `make reset-seed` – clear seeded items and allow reseeding.

## Sample Requests

```bash
curl http://localhost:8000/health

curl http://localhost:8000/version

curl -X POST http://localhost:8000/items/presign \
  -H 'Content-Type: application/json' \
  -d '{"contentType": "image/jpeg", "fileName": "top.jpg"}'

curl "http://localhost:8000/items?category=top&q=nike"

curl "http://localhost:8000/items?include_deleted=true"  # include soft-deleted rows (admin tooling)

curl -X PATCH http://localhost:8000/items/<item-id> \
  -H 'Content-Type: application/json' \
  -d '{"brand": "Uniqlo", "color": "navy", "tags": ["minimal"]}'

curl -X DELETE http://localhost:8000/items/<item-id>

# Sample wardrobe payload (truncated)
{
  "id": "...",
  "imageUrl": "https://bucket.s3.us-east-1.amazonaws.com/user/.../orig.jpg",
  "thumbUrl": "https://bucket.s3.us-east-1.amazonaws.com/user/.../thumb.jpg",
  "mediumUrl": "https://bucket.s3.us-east-1.amazonaws.com/user/.../medium.jpg",
  "imageMetadata": {
    "width": 2048,
    "height": 1365,
    "bytes": 325486,
    "mimeType": "image/jpeg",
    "checksum": "...sha256..."
  },
  "tags": ["minimal"]
}
```

## Seeding the Local Wardrobe

On first run the API seeds a curated dataset when `APP_ENV=local` and
`SEED_ON_START=true`. The process is idempotent—the applied seed key is recorded
in the `seeds` table so restarts do not duplicate rows. Use `make seed` to run
the pipeline manually or `make reset-seed` to clear the marker and generated
media before reseeding. Configuration lives in `app/seed/seed_sources.yaml`.

## Docker

For a simple container build:

```bash
docker build -t styleus-api .
docker run --rm -p 8000:8000 --env-file .env styleus-api
```

## Testing

Tests run against SQLite with AWS calls mocked via lightweight stubs:

```bash
make test
```

### Uploads in local development

When `APP_ENV=local`, the `/items/presign` endpoint returns an upload URL that targets the API itself (`PUT /items/uploads/{itemId}`) so the frontend can stream files without real S3 credentials. In staging/production the service falls back to presigned S3 URLs and requires valid AWS configuration.

## Upload Modes

- **S3 mode** (default when `AWS_REGION` and `S3_BUCKET_NAME` are present): uploads are presigned to S3 and the final `image_url` is constructed from the bucket/region unless the client supplies an explicit URL.
- **Local mode** (default when S3 variables are absent): uploads stream directly to the API, are written under `MEDIA_ROOT/<item_id>/{orig,medium,thumb}.jpg`, and are exposed via `MEDIA_URL_PATH`.

Every completed upload extracts metadata (width, height, bytes, mime type, checksum) and publishes jpeg variants for thumbnail and medium sizes. These appear on the wardrobe item JSON as `imageUrl`, `mediumUrl`, `thumbUrl`, and `imageMetadata`.

## Local Seeding

The API can auto-populate a development database with 30 curated wardrobe
entries bundled under `app/seed/`. By default this runs on the first startup in
`APP_ENV=local`; disable by setting `SEED_ON_START=false`. Manual control is
available via `make seed` / `make reset-seed`, and the dataset configuration is
documented in `app/seed/README.md`.

### Local upload walkthrough

```bash
# 1. Request an upload slot (returns /items/uploads/<id>)
curl -s -X POST :8000/items/presign \
  -H "Content-Type: application/json" \
  -d '{"contentType":"image/jpeg","fileName":"top.jpg"}'

# 2. Upload the file directly to the API
curl -s -X PUT :8000/items/uploads/<itemId> \
  -H "Content-Type: image/jpeg" \
  -H "X-File-Name: top.jpg" \
  --data-binary @top.jpg

# 3. Finalise the upload so the record stores the served URL
curl -s -X POST :8000/items/<itemId>/complete-upload \
  -H "Content-Type: application/json" \
  -d '{"fileName":"top.jpg"}'
```

## Post-Implementation Sanity Checklist

- `docker run -p 5432:5432 postgres:16`
- `make setup && make upgrade && make run`
- `curl :8000/health`
- `curl -X POST :8000/items/presign -H 'Content-Type: application/json' -d '{"contentType":"image/jpeg","fileName":"t.jpg"}'`
- `curl :8000/items?category=top&q=nike`
- `pytest -q`
