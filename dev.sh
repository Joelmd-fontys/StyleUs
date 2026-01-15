#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT_DIR/services/api"
WEB_DIR="$ROOT_DIR/apps/web"
VENV_DIR="$API_DIR/.venv"
PYPROJECT_FILE="$API_DIR/pyproject.toml"
PYPROJECT_HASH_FILE="$VENV_DIR/.pyproject.sha256"
DB_CONTAINER="styleus-db"
DB_COMPOSE_FILE="$API_DIR/docker-compose.yml"

BACKEND_PID=""
FRONTEND_PID=""
STARTED_DB=0
CLEANED_UP=0

log() {
  printf "\n==> %s\n" "$1"
}

fail() {
  printf "\nERROR: %s\n" "$1" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "$2"
  fi
}

cleanup() {
  # Avoid double cleanup if EXIT and INT both fire.
  if [ "$CLEANED_UP" -eq 1 ]; then
    return
  fi
  CLEANED_UP=1

  set +e
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend..."
    kill "$BACKEND_PID" 2>/dev/null
    wait "$BACKEND_PID" 2>/dev/null
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend..."
    kill "$FRONTEND_PID" 2>/dev/null
    wait "$FRONTEND_PID" 2>/dev/null
  fi

  if [ "$STARTED_DB" -eq 1 ]; then
    log "Stopping database container..."
    docker compose -f "$DB_COMPOSE_FILE" down >/dev/null 2>&1
  fi
}

trap cleanup EXIT INT TERM

compute_hash() {
  python3 - <<'PY' "$1"
import hashlib
import pathlib
path = pathlib.Path(__import__("sys").argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

check_prereqs() {
  log "Checking prerequisites..."
  require_cmd docker "Docker is required. Please install Docker Desktop or Docker Engine."
  if ! docker info >/dev/null 2>&1; then
    fail "Docker is not running. Start Docker Desktop/daemon and retry."
  fi
  if ! docker compose version >/dev/null 2>&1; then
    fail "Docker Compose V2 is required (docker compose). Please upgrade Docker."
  fi

  require_cmd node "Node.js is required. Install it from https://nodejs.org/."
  require_cmd npm "npm is required. Install it with Node.js from https://nodejs.org/."
  require_cmd python3 "Python 3 is required. Install it from https://www.python.org/downloads/."

  PY_VER="$(python3 - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
PY
)"
  python3 - <<'PY' || fail "Python 3.11+ is required (pyproject.toml requires >=3.11,<3.13). Current: ${PY_VER}"
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
}

ensure_backend_env_file() {
  if [ ! -f "$API_DIR/.env" ]; then
    if [ -f "$API_DIR/.env.example" ]; then
      log "No services/api/.env found. Creating one from .env.example..."
      cp "$API_DIR/.env.example" "$API_DIR/.env"
    else
      fail "Missing services/api/.env. Please create it to continue."
    fi
  fi
}

load_backend_env() {
  if [ -f "$API_DIR/.env" ]; then
    # Export variables for Alembic and the app.
    set -a
    # shellcheck source=/dev/null
    . "$API_DIR/.env"
    set +a
  fi
}

ensure_backend_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi
}

install_backend_deps() {
  local install_needed=0
  local current_hash=""

  if [ ! -d "$VENV_DIR" ]; then
    install_needed=1
  else
    current_hash="$(compute_hash "$PYPROJECT_FILE")"
    if [ ! -f "$PYPROJECT_HASH_FILE" ] || [ "$(cat "$PYPROJECT_HASH_FILE")" != "$current_hash" ]; then
      install_needed=1
    fi
  fi

  if [ "$install_needed" -eq 1 ]; then
    log "Installing backend dependencies..."
    ensure_backend_venv
    current_hash="${current_hash:-$(compute_hash "$PYPROJECT_FILE")}"
    (
      cd "$API_DIR"
      "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
      "$VENV_DIR/bin/python" -m pip install -e ".[dev]"
    )
    echo "$current_hash" >"$PYPROJECT_HASH_FILE"
  else
    log "Backend dependencies already installed."
  fi
}

start_database() {
  log "Starting database (Docker)..."
  local status
  status="$(docker inspect -f '{{.State.Status}}' "$DB_CONTAINER" 2>/dev/null || true)"

  if [ "$status" != "running" ]; then
    docker compose -f "$DB_COMPOSE_FILE" up -d
    STARTED_DB=1
  else
    log "Database container already running. Reusing it."
  fi
}

wait_for_database() {
  log "Waiting for database to become healthy..."
  local retries=30
  local attempt=1
  while [ "$attempt" -le "$retries" ]; do
    local health
    health="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null || true)"
    if [ "$health" = "healthy" ]; then
      log "Database is healthy."
      return
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
  fail "Database did not become healthy. Check Docker logs for $DB_CONTAINER."
}

run_migrations() {
  log "Running migrations (alembic upgrade head)..."
  (
    cd "$API_DIR"
    "$VENV_DIR/bin/alembic" upgrade head
  )
}

ensure_frontend_env() {
  if [ ! -f "$WEB_DIR/.env.local" ] && [ -f "$WEB_DIR/.env.example" ]; then
    log "No apps/web/.env.local found. Creating one from .env.example..."
    cp "$WEB_DIR/.env.example" "$WEB_DIR/.env.local"
  fi
}

install_frontend_deps() {
  if [ ! -d "$WEB_DIR/node_modules" ]; then
    log "Installing frontend dependencies..."
    (
      cd "$WEB_DIR"
      npm ci
    )
  fi
}

start_backend() {
  log "Starting backend (FastAPI @ http://localhost:8000)..."
  (
    cd "$API_DIR"
    exec "$VENV_DIR/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  log "Starting frontend (Vite @ http://localhost:5173)..."
  (
    cd "$WEB_DIR"
    exec npm run dev -- --host 0.0.0.0 --port 5173
  ) &
  FRONTEND_PID=$!
}

main() {
  cd "$ROOT_DIR"

  check_prereqs
  ensure_backend_env_file
  load_backend_env
  install_backend_deps
  start_database
  wait_for_database
  run_migrations

  ensure_frontend_env
  install_frontend_deps

  start_backend
  start_frontend

  log "All set. API: http://localhost:8000 | Web: http://localhost:5173"
  log "Press Ctrl+C to stop both services."

  set +e
  if wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null; then
    exit_code=$?
  else
    # Bash <4 doesn't support wait -n; poll for an exited child.
    while :; do
      for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
        if ! kill -0 "$pid" 2>/dev/null; then
          wait "$pid"
          exit_code=$?
          break 2
        fi
      done
      sleep 1
    done
  fi
  log "One of the services exited (code $exit_code). Shutting down..."
  cleanup
  exit "$exit_code"
}

main "$@"
