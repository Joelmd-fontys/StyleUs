from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.seed import runner as seed_runner
from app.utils import storage as storage_utils


class FakeStorageAdapter:
    def __init__(self) -> None:
        self.uploaded_objects: dict[str, bytes] = {}
        self.deleted_objects: list[str] = []

    def upload_bytes(
        self,
        object_path: str,
        *,
        data: bytes,
        content_type: str,
        upsert: bool = True,
    ) -> None:
        _ = content_type, upsert
        self.uploaded_objects[object_path] = data

    def delete_objects(self, object_paths: list[str]) -> None:
        self.deleted_objects.extend(object_paths)


def test_seed_creates_items_and_is_idempotent(tmp_path, monkeypatch, db_session):
    seed_user_id = uuid.uuid4()
    monkeypatch.setenv("LOCAL_AUTH_USER_ID", str(seed_user_id))
    monkeypatch.setenv("LOCAL_AUTH_EMAIL", "seed-user@styleus.invalid")
    monkeypatch.setenv("RUN_SEED_ON_START", "true")
    monkeypatch.setenv("SEED_KEY", "test-local-seed")
    monkeypatch.setenv("SEED_LIMIT", "3")
    fake_storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: fake_storage)

    get_settings.cache_clear()
    settings = get_settings()

    session_factory = sessionmaker(
        bind=db_session.bind,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(seed_runner, "SessionLocal", session_factory)

    summary = seed_runner.run_seed(
        settings=settings,
        force=True,
        limit=3,
        seed_key="test-local-seed",
    )
    assert summary.inserted == 3
    assert summary.failed == 0

    with session_factory() as session:
        items = session.scalars(select(WardrobeItem)).all()
        assert len(items) == 3
        for item in items:
            assert item.user_id == seed_user_id
            assert item.image_object_path == f"users/{seed_user_id}/{item.id}/orig.jpg"
            assert item.image_medium_object_path == f"users/{seed_user_id}/{item.id}/medium.jpg"
            assert item.image_thumb_object_path == f"users/{seed_user_id}/{item.id}/thumb.jpg"
        user = session.get(User, seed_user_id)
        assert user is not None
        assert user.email == "seed-user@styleus.invalid"

    repeat = seed_runner.run_seed(
        settings=settings,
        limit=3,
        seed_key="test-local-seed",
    )
    assert repeat.inserted == 0
    assert repeat.skipped >= 1

    reset_summary = seed_runner.reset_seed(settings=settings, seed_key="test-local-seed")
    assert reset_summary.removed == 3
    with session_factory() as session:
        remaining = session.scalars(select(WardrobeItem)).all()
        assert len(remaining) == 0
    assert len(fake_storage.uploaded_objects) == 9
    assert len(fake_storage.deleted_objects) == 9


def test_seed_rejected_outside_local_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://styleus-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
    monkeypatch.setenv("RUN_SEED_ON_START", "false")
    monkeypatch.delenv("LOCAL_AUTH_BYPASS", raising=False)

    get_settings.cache_clear()
    settings = get_settings()

    with pytest.raises(ValueError, match="APP_ENV=local"):
        seed_runner.run_seed(settings=settings, force=True, limit=1, seed_key="staging-seed")

    with pytest.raises(ValueError, match="APP_ENV=local"):
        seed_runner.reset_seed(settings=settings, seed_key="staging-seed")
