#!/usr/bin/env python3
from __future__ import annotations

import os
import time


def _set_default_env() -> None:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/styleus"
    )
    os.environ.setdefault("SUPABASE_URL", "https://styleus-ci.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "styleus-ci-service-role")
    os.environ.setdefault("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
    os.environ.setdefault("LOCAL_AUTH_BYPASS", "true")
    os.environ.setdefault("RUN_MIGRATIONS_ON_START", "false")
    os.environ.setdefault("RUN_SEED_ON_START", "false")
    os.environ.setdefault("AI_JOB_POLL_INTERVAL_SECONDS", "0.1")
    os.environ.setdefault("APP_VERSION", "ci-smoke")


def main() -> int:
    _set_default_env()

    from fastapi.testclient import TestClient

    from app.ai import pipeline
    from app.core.config import get_settings
    from app.main import create_app
    from app.worker import AIWorker

    get_settings.cache_clear()

    application = create_app(start_worker=False)
    with TestClient(application) as client:
        response = client.get("/health")
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ok" or payload.get("database") != "ok":
            raise RuntimeError(f"Unexpected /health payload: {payload}")
    print("FastAPI startup and /health verification passed.")

    warm_up_calls = {"count": 0}
    run_once_calls = {"count": 0}

    pipeline.warm_up = lambda: warm_up_calls.__setitem__("count", warm_up_calls["count"] + 1) or True

    original_run_once = AIWorker.run_once

    def run_once_and_stop(self: AIWorker) -> bool:
        run_once_calls["count"] += 1
        self.request_shutdown(reason="ci_smoke_test_complete")
        return False

    AIWorker.run_once = run_once_and_stop
    try:
        worker = AIWorker(get_settings())
        worker.start_in_background(thread_name="styleus-ci-worker")
        deadline = time.time() + 5
        while time.time() < deadline and run_once_calls["count"] == 0:
            time.sleep(0.05)
        if run_once_calls["count"] == 0:
            raise RuntimeError("AI worker thread did not start within 5 seconds")
        if not worker.join(timeout=5):
            raise RuntimeError("AI worker thread did not exit cleanly after the smoke test")
    finally:
        AIWorker.run_once = original_run_once

    if warm_up_calls["count"] != 1:
        raise RuntimeError(f"Expected one worker warm-up call, saw {warm_up_calls['count']}")

    print("AI worker initialization verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
