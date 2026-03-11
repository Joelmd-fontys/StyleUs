from __future__ import annotations

import datetime as dt
import io
import uuid
from contextlib import nullcontext
from pathlib import Path

import pytest
from PIL import Image

from app.ai import color
from app.ai import tasks as ai_tasks
from app.ai.pipeline import PipelineResult
from app.api.deps import DEFAULT_USER_ID
from app.core.config import get_settings
from app.models.ai_job import AIJob, AIJobStatus
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.services import ai_jobs as ai_jobs_service
from app.utils import storage as storage_utils
from app import worker as worker_module


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
