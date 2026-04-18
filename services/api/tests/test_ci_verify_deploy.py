from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_verify_deploy_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "verify_deploy.py"
    spec = importlib.util.spec_from_file_location("verify_deploy", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify_deploy = _load_verify_deploy_module()


def test_api_health_requires_database_ready() -> None:
    result = verify_deploy.evaluate_api_response(200, '{"status":"ok","database":"starting"}')
    assert result.ok is False
    assert "database=ok" in result.message


def test_api_health_passes_for_ready_payload() -> None:
    result = verify_deploy.evaluate_api_response(200, '{"status":"ok","database":"ok"}')
    assert result.ok is True


def test_worker_health_rejects_disabled_mode() -> None:
    result = verify_deploy.evaluate_worker_response(
        200,
        '{"status":"ok","service":"ai-worker","mode":"disabled","pending_jobs":0,"running_jobs":0}',
    )
    assert result.ok is False
    assert "mode=disabled" in result.message


def test_worker_health_passes_for_enabled_mode() -> None:
    result = verify_deploy.evaluate_worker_response(
        200,
        '{"status":"ok","service":"ai-worker","pending_jobs":1,"running_jobs":0}',
    )
    assert result.ok is True


def test_worker_health_requires_ai_worker_service_identity() -> None:
    result = verify_deploy.evaluate_worker_response(
        200,
        '{"status":"ok","service":"api","pending_jobs":1,"running_jobs":0}',
    )
    assert result.ok is False
    assert "service='ai-worker'" in result.message


def test_worker_health_requires_queue_counts() -> None:
    result = verify_deploy.evaluate_worker_response(
        200,
        '{"status":"ok","service":"ai-worker"}',
    )
    assert result.ok is False
    assert "pending_jobs" in result.message


def test_frontend_health_requires_html_doctype() -> None:
    result = verify_deploy.evaluate_frontend_response(
        200,
        "<html><body>missing doctype</body></html>",
    )
    assert result.ok is False
    assert "doctype html" in result.message.lower()


def test_frontend_health_accepts_html_document() -> None:
    result = verify_deploy.evaluate_frontend_response(
        200,
        "<!DOCTYPE html><html><body>ok</body></html>",
    )
    assert result.ok is True
