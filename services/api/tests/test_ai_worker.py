from __future__ import annotations

import datetime as dt
import io
import uuid
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main as main_module
from app import worker_service as worker_service_module
from app.ai import color
from app.ai import tasks as ai_tasks
from app.ai import worker as worker_module
from app.ai.pipeline import PipelineResult
from app.api.deps import DEFAULT_USER_ID
from app.core.config import get_settings
from app.models.ai_job import AIJob, AIJobStatus
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.services import ai_jobs as ai_jobs_service
from app.utils import storage as storage_utils


class FakeStorageAdapter:
    def __init__(self) -> None:
        self.objects: dict[str, storage_utils.DownloadedObject] = {}
        self.downloaded_paths: list[str] = []

    def download_object(self, object_path: str) -> storage_utils.DownloadedObject:
        self.downloaded_paths.append(object_path)
        return self.objects[object_path]


def _prepare_worker_settings(
    monkeypatch: pytest.MonkeyPatch,
    media_root: Path,
    storage: FakeStorageAdapter,
    session,
    **env: str,
) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    settings = get_settings()
    ai_tasks.settings = settings
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: storage)
    monkeypatch.setattr(worker_module, "SessionLocal", lambda: nullcontext(session))
    if session.get(User, DEFAULT_USER_ID) is None:
        session.add(User(id=DEFAULT_USER_ID, email="worker@example.com"))
        session.commit()


def _create_image_bytes() -> bytes:
    image = Image.new("RGB", (128, 128), color=(120, 90, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _mock_pipeline_result() -> PipelineResult:
    return PipelineResult(
        colors=color.ColorResult(
            primary_color="Camel",
            secondary_color="Tan",
            confidence=0.88,
            secondary_confidence=0.71,
        ),
        clip={
            "category": "outerwear",
            "category_confidence": 0.91,
            "materials": [("wool", 0.83)],
            "style_tags": [("heritage", 0.79)],
            "subcategory": "coat",
            "subcategory_confidence": 0.8,
            "scores": {
                "category": {"outerwear": 0.91},
                "materials": {"wool": 0.83},
                "style_tags": {"heritage": 0.79},
                "subcategory": {"coat": 0.8},
            },
        },
        cached=False,
    )


def test_worker_processes_pending_job_and_marks_completed(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_worker_settings(monkeypatch, tmp_path, storage, db_session)

    item_id = uuid.uuid4()
    object_path = f"users/{DEFAULT_USER_ID}/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path=object_path,
    )
    db_session.add(item)
    db_session.commit()
    job = ai_jobs_service.enqueue_item_job(db_session, item)

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: _mock_pipeline_result())

    worker = worker_module.AIWorker(get_settings())
    assert worker.run_once() is True

    db_session.expire_all()
    refreshed = db_session.get(WardrobeItem, item_id)
    job = db_session.get(AIJob, job.id)

    assert refreshed is not None
    assert refreshed.category == "outerwear"
    assert refreshed.subcategory == "coat"
    assert refreshed.primary_color == "Camel"
    assert refreshed.secondary_color == "Tan"
    assert refreshed.ai_materials == ["wool"]
    assert refreshed.ai_style_tags == ["heritage"]
    assert sorted(tag.tag for tag in refreshed.tags) == ["heritage", "wool"]
    assert job is not None
    assert job.status == AIJobStatus.COMPLETED.value
    assert job.attempts == 1
    assert job.completed_at is not None
    assert job.result_payload is not None
    assert job.result_payload["category"] == "outerwear"
    assert job.result_payload["subcategory"] == "coat"
    assert job.result_payload["primary_color"] == "Camel"
    assert job.result_payload["secondary_color"] == "Tan"
    assert job.result_payload["tags"] == ["wool", "heritage"]


def test_worker_retries_job_until_failure_limit(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_worker_settings(
        monkeypatch,
        tmp_path,
        storage,
        db_session,
        AI_JOB_MAX_ATTEMPTS="2",
    )

    item_id = uuid.uuid4()
    object_path = f"users/{DEFAULT_USER_ID}/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path=object_path,
    )
    db_session.add(item)
    db_session.commit()
    job = ai_jobs_service.enqueue_item_job(db_session, item)

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )

    def _raise(path: Path) -> PipelineResult:
        raise RuntimeError("clip unavailable")

    monkeypatch.setattr(ai_tasks.pipeline, "run", _raise)

    worker = worker_module.AIWorker(get_settings())
    assert worker.run_once() is True

    db_session.expire_all()
    first_job = db_session.get(AIJob, job.id)
    assert first_job is not None
    assert first_job.status == AIJobStatus.PENDING.value
    assert first_job.attempts == 1
    assert "clip unavailable" in (first_job.error_message or "")

    assert worker.run_once() is True

    db_session.expire_all()
    failed_job = db_session.get(AIJob, job.id)
    assert failed_job is not None
    assert failed_job.status == AIJobStatus.FAILED.value
    assert failed_job.attempts == 2
    assert failed_job.completed_at is not None


def test_worker_prefers_medium_variant_for_inference(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_worker_settings(monkeypatch, tmp_path, storage, db_session)

    item_id = uuid.uuid4()
    orig_path = f"users/{DEFAULT_USER_ID}/{item_id}/orig.jpg"
    medium_path = f"users/{DEFAULT_USER_ID}/{item_id}/medium.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path=orig_path,
        image_medium_object_path=medium_path,
        image_checksum="a" * 64,
    )
    db_session.add(item)
    db_session.commit()
    ai_jobs_service.enqueue_item_job(db_session, item)

    storage.objects[medium_path] = storage_utils.DownloadedObject(
        object_path=medium_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: _mock_pipeline_result())

    worker = worker_module.AIWorker(get_settings())
    assert worker.run_once() is True
    assert storage.downloaded_paths == [medium_path]


def test_fastapi_lifespan_starts_and_stops_embedded_worker(monkeypatch):
    lifecycle: list[object] = []

    class FakeWorker:
        def __init__(self, settings) -> None:
            lifecycle.append(("init", settings.ai_job_poll_interval_seconds))

        def start_in_background(self) -> None:
            lifecycle.append("started")

        def request_shutdown(self, *, reason: str) -> None:
            lifecycle.append(("shutdown", reason))

        def join(self, timeout: float | None = None) -> bool:
            lifecycle.append(("join", timeout))
            return True

    monkeypatch.setattr(main_module, "_get_ai_worker_class", lambda: FakeWorker)

    application = main_module.create_app(start_worker=True)

    with TestClient(application):
        assert lifecycle == [("init", get_settings().ai_job_poll_interval_seconds), "started"]

    assert lifecycle == [
        ("init", get_settings().ai_job_poll_interval_seconds),
        "started",
        ("shutdown", "lifespan_shutdown"),
        ("join", 30.0),
    ]


def test_fastapi_lifespan_skips_worker_by_default(monkeypatch):
    lifecycle: list[object] = []

    class FakeWorker:
        def __init__(self, settings) -> None:
            lifecycle.append(("init", settings.ai_job_poll_interval_seconds))

    monkeypatch.setattr(main_module, "_get_ai_worker_class", lambda: FakeWorker)

    application = main_module.create_app()

    with TestClient(application):
        assert lifecycle == []


def test_worker_service_health_reports_worker_status(monkeypatch):
    lifecycle: list[object] = []

    class FakeWorker:
        def __init__(self, settings) -> None:
            lifecycle.append(("init", settings.ai_job_poll_interval_seconds))

        def start_in_background(self, *, thread_name: str = "styleus-ai-worker") -> bool:
            lifecycle.append(("started", thread_name))
            return True

        def request_shutdown(self, *, reason: str) -> None:
            lifecycle.append(("shutdown", reason))

        def join(self, timeout: float | None = None) -> bool:
            lifecycle.append(("join", timeout))
            return True

        def is_running(self) -> bool:
            return True

        def thread_alive(self) -> bool:
            return True

        def snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(memory_rss_mb=128.5, last_error=None)

    monkeypatch.setattr(worker_service_module, "_get_ai_worker_class", lambda: FakeWorker)
    monkeypatch.setattr(worker_service_module, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        worker_service_module.ai_jobs_service,
        "get_queue_counts",
        lambda session: {"pending": 2, "running": 1, "completed": 0, "failed": 0},
    )

    application = worker_service_module.create_worker_app()
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-worker",
        "pending_jobs": 2,
        "running_jobs": 1,
        "memory_rss_mb": 128.5,
    }
    assert lifecycle == [
        ("init", get_settings().ai_job_poll_interval_seconds),
        ("started", "styleus-ai-worker-service"),
        ("shutdown", "worker_service_shutdown"),
        ("join", 30.0),
    ]


def test_worker_service_health_reports_disabled_mode_when_classifier_is_off(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_CLASSIFIER", "false")
    get_settings.cache_clear()
    lifecycle: list[object] = []

    class FakeWorker:
        def __init__(self, settings) -> None:
            lifecycle.append(("init", settings.ai_enable_classifier))

        def start_in_background(self, *, thread_name: str = "styleus-ai-worker") -> bool:
            lifecycle.append(("started", thread_name))
            return False

        def request_shutdown(self, *, reason: str) -> None:
            lifecycle.append(("shutdown", reason))

        def join(self, timeout: float | None = None) -> bool:
            lifecycle.append(("join", timeout))
            return True

        def is_running(self) -> bool:
            return False

        def thread_alive(self) -> bool:
            return False

        def snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(memory_rss_mb=96.0, last_error=None)

    monkeypatch.setattr(worker_service_module, "_get_ai_worker_class", lambda: FakeWorker)
    monkeypatch.setattr(worker_service_module, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        worker_service_module.ai_jobs_service,
        "get_queue_counts",
        lambda session: {"pending": 0, "running": 0, "completed": 0, "failed": 0},
    )

    application = worker_service_module.create_worker_app()
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-worker",
        "mode": "disabled",
        "pending_jobs": 0,
        "running_jobs": 0,
        "memory_rss_mb": 96.0,
    }
    assert lifecycle == [
        ("init", False),
        ("started", "styleus-ai-worker-service"),
        ("shutdown", "worker_service_shutdown"),
        ("join", 30.0),
    ]
    get_settings.cache_clear()


def test_worker_service_health_fails_when_worker_unavailable(monkeypatch):
    class FakeWorker:
        def __init__(self, settings) -> None:
            del settings

        def start_in_background(self, *, thread_name: str = "styleus-ai-worker") -> bool:
            del thread_name
            return True

        def request_shutdown(self, *, reason: str) -> None:
            del reason

        def join(self, timeout: float | None = None) -> bool:
            del timeout
            return True

        def is_running(self) -> bool:
            return False

        def thread_alive(self) -> bool:
            return False

        def snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(memory_rss_mb=None, last_error="worker died")

    monkeypatch.setattr(worker_service_module, "_get_ai_worker_class", lambda: FakeWorker)
    monkeypatch.setattr(worker_service_module, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        worker_service_module.ai_jobs_service,
        "get_queue_counts",
        lambda session: {"pending": 0, "running": 0, "completed": 0, "failed": 0},
    )

    application = worker_service_module.create_worker_app()
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "worker died"}


def test_claim_next_job_reclaims_stale_running_job(db_session):
    user = db_session.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(id=DEFAULT_USER_ID, email="queue@example.com")
        db_session.add(user)
        db_session.commit()

    item = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path="users/test/orig.jpg",
    )
    db_session.add(item)
    db_session.commit()

    started_at = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=10)
    job = AIJob(
        item_id=item.id,
        status=AIJobStatus.RUNNING.value,
        attempts=1,
        started_at=started_at,
    )
    db_session.add(job)
    db_session.commit()

    lease = ai_jobs_service.claim_next_job(
        db_session,
        max_attempts=3,
        stale_after=dt.timedelta(minutes=5),
    )

    assert lease is not None
    assert lease.job_id == job.id
    assert lease.attempts == 2

    db_session.expire_all()
    refreshed = db_session.get(AIJob, job.id)
    assert refreshed is not None
    assert refreshed.status == AIJobStatus.RUNNING.value
    assert refreshed.attempts == 2
    assert refreshed.started_at is not None
    assert refreshed.started_at > started_at


def test_claim_next_job_marks_deleted_pending_jobs_failed(db_session):
    user = db_session.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(id=DEFAULT_USER_ID, email="queue@example.com")
        db_session.add(user)
        db_session.commit()

    deleted_item = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path="users/test/deleted.jpg",
        deleted_at=dt.datetime.now(dt.UTC),
    )
    active_item = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_object_path="users/test/active.jpg",
    )
    db_session.add_all([deleted_item, active_item])
    db_session.commit()

    deleted_job = AIJob(
        item_id=deleted_item.id,
        status=AIJobStatus.PENDING.value,
        attempts=0,
    )
    active_job = AIJob(
        item_id=active_item.id,
        status=AIJobStatus.PENDING.value,
        attempts=0,
    )
    db_session.add_all([deleted_job, active_job])
    db_session.commit()

    lease = ai_jobs_service.claim_next_job(
        db_session,
        max_attempts=3,
        stale_after=dt.timedelta(minutes=5),
    )

    assert lease is not None
    assert lease.item_id == active_item.id

    db_session.expire_all()
    refreshed_deleted_job = db_session.get(AIJob, deleted_job.id)
    assert refreshed_deleted_job is not None
    assert refreshed_deleted_job.status == AIJobStatus.FAILED.value
    assert refreshed_deleted_job.error_message == "Wardrobe item deleted before AI enrichment"
