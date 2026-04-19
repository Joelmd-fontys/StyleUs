from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_importtime(module_name: str) -> str:
    env = os.environ.copy()
    env.setdefault("APP_ENV", "local")
    env.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres")
    env.setdefault("SUPABASE_URL", "https://styleus-test.supabase.co")
    env.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    env.setdefault("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
    env.setdefault("LOCAL_AUTH_BYPASS", "true")
    env.setdefault("RUN_MIGRATIONS_ON_START", "false")
    env.setdefault("RUN_SEED_ON_START", "false")

    completed = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", f"import {module_name}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stderr


def test_api_runtime_does_not_import_ai_stack() -> None:
    output = _run_importtime("app.main")

    assert "app.ai.worker" not in output
    assert "app.ai.pipeline" not in output
    assert "sklearn" not in output
    assert "open_clip" not in output
    assert "torch" not in output


def test_worker_service_import_does_not_eagerly_load_model_runtime() -> None:
    output = _run_importtime("app.worker_service")

    assert "open_clip" not in output
    assert "torch" not in output


def test_worker_cli_import_does_not_eagerly_load_model_runtime() -> None:
    output = _run_importtime("app.worker")

    assert "app.ai.worker" not in output
    assert "open_clip" not in output
    assert "torch" not in output
