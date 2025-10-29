from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.wardrobe import WardrobeItem
from app.seed import runner as seed_runner


def test_seed_creates_items_and_is_idempotent(tmp_path, monkeypatch, db_session):
    media_root = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("SEED_ON_START", "true")
    monkeypatch.setenv("SEED_KEY", "test-local-seed")
    monkeypatch.setenv("SEED_LIMIT", "3")

    get_settings.cache_clear()
    settings = get_settings()

    session_factory = sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(seed_runner, "SessionLocal", session_factory)

    summary = seed_runner.run_seed(settings=settings, force=True, limit=3, seed_key="test-local-seed")
    assert summary.inserted == 3
    assert summary.failed == 0

    with session_factory() as session:
        items = session.scalars(select(WardrobeItem)).all()
        assert len(items) == 3
        for item in items:
            item_dir = Path(settings.media_root_path) / str(item.id)
            assert (item_dir / "orig.jpg").exists()
            assert (item_dir / "medium.jpg").exists()
            assert (item_dir / "thumb.jpg").exists()

    repeat = seed_runner.run_seed(settings=settings, limit=3, seed_key="test-local-seed")
    assert repeat.inserted == 0
    assert repeat.skipped >= 1

    reset_summary = seed_runner.reset_seed(settings=settings, seed_key="test-local-seed")
    assert reset_summary.removed == 3
    with session_factory() as session:
        remaining = session.scalars(select(WardrobeItem)).all()
        assert len(remaining) == 0
    assert not any(media_root.glob("**/orig.jpg"))
