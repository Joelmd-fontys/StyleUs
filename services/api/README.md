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
| `CORS_ORIGINS` | CSV of allowed origins | `http://localhost:5173` |

The application fails fast in staging/production if any required variable is missing.

## Local Development

1. Start PostgreSQL (example using Docker):
   ```bash
   docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=styleus postgres:16
   ```
2. Configure a local `.env` (one is provided with development defaults) or tweak as needed. Example:
   ```env
   APP_ENV=local
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/styleus
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=styleus-dev
   CORS_ORIGINS=http://localhost:5173
   API_KEY=
   ```
3. Install dependencies and run migrations:
   ```bash
   make setup
   make upgrade
   ```
4. Launch the API:
   ```bash
   make run
   ```

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

## Sample Requests

```bash
curl http://localhost:8000/health

curl http://localhost:8000/version

curl -X POST http://localhost:8000/items/presign \
  -H 'Content-Type: application/json' \
  -d '{"contentType": "image/jpeg", "fileName": "top.jpg"}'

curl "http://localhost:8000/items?category=top&q=nike"

curl -X PATCH http://localhost:8000/items/<item-id> \
  -H 'Content-Type: application/json' \
  -d '{"brand": "Uniqlo", "color": "navy", "tags": ["minimal"]}'
```

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

## Post-Implementation Sanity Checklist

- `docker run -p 5432:5432 postgres:16`
- `make setup && make upgrade && make run`
- `curl :8000/health`
- `curl -X POST :8000/items/presign -H 'Content-Type: application/json' -d '{"contentType":"image/jpeg","fileName":"t.jpg"}'`
- `curl :8000/items?category=top&q=nike`
- `pytest -q`
