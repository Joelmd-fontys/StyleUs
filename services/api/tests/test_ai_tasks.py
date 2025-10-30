from __future__ import annotations

import datetime as dt
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
from app.models.wardrobe import ItemTag, WardrobeItem


def _prepare_settings(
    monkeypatch: pytest.MonkeyPatch,
    media_root: Path,
    session=None,
    **env: str,
) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("MEDIA_URL_PATH", "/media")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    ai_tasks.settings = get_settings()
    if session is not None:
        monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: nullcontext(session))


def _create_local_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (128, 128), color=(220, 180, 120))
    image.save(path, format="JPEG")


def _mock_pipeline_result(
    *,
    primary: str,
    secondary: str | None,
    color_conf: float,
    secondary_conf: float | None,
    category: str,
    category_conf: float,
    subcategory: str | None,
    sub_conf: float | None,
    materials: list[tuple[str, float]],
    styles: list[tuple[str, float]],
) -> PipelineResult:
    scores_category = {category: category_conf}
    scores_sub = {subcategory: sub_conf} if subcategory and sub_conf is not None else {}
    score_materials = dict(materials)
    score_styles = dict(styles)
    return PipelineResult(
        colors=color.ColorResult(
            primary_color=primary,
            secondary_color=secondary,
            confidence=color_conf,
            secondary_confidence=secondary_conf,
        ),
        clip={
            "category": category,
            "category_confidence": category_conf,
            "subcategory": subcategory,
            "subcategory_confidence": sub_conf,
            "materials": materials,
            "styles": styles,
            "scores": {
                "category": scores_category,
                "subcategory": scores_sub,
                "materials": score_materials,
                "styles": score_styles,
            },
        },
        cached=False,
    )


def test_classify_and_update_item_populates_empty_fields(db_session, tmp_path, monkeypatch):
    _prepare_settings(monkeypatch, tmp_path, session=db_session)
    item_id = uuid.uuid4()
    image_rel = f"/media/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="unspecified",
        brand=None,
        image_url=image_rel,
    )
    db_session.add(item)
    db_session.commit()

    _create_local_image(tmp_path / str(item_id) / "orig.jpg")

    pipeline_result = _mock_pipeline_result(
        primary="Camel",
        secondary="Tan",
        color_conf=0.82,
        secondary_conf=0.74,
        category="outerwear",
        category_conf=0.92,
        subcategory="coat",
        sub_conf=0.84,
        materials=[("leather", 0.88)],
        styles=[("heritage", 0.81)],
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: pipeline_result)

    ai_tasks.classify_and_update_item(item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    assert refreshed.category == "outerwear"
    assert refreshed.subcategory == "coat"
    assert refreshed.primary_color == "Camel"
    assert refreshed.secondary_color == "Tan"
    assert refreshed.color == "Camel"
    assert refreshed.ai_confidence == pytest.approx(0.92)
    refreshed_tags = sorted(tag.tag for tag in refreshed.tags)
    assert refreshed_tags == ["heritage", "leather"]


def test_classify_and_update_item_respects_existing_data(db_session, tmp_path, monkeypatch):
    _prepare_settings(monkeypatch, tmp_path, session=db_session)
    item_id = uuid.uuid4()
    image_rel = f"/media/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="top",
        color="blue",
        brand="Acme",
        image_url=image_rel,
    )
    item.tags.append(ItemTag(tag="casual"))
    db_session.add(item)
    db_session.commit()

    _create_local_image(tmp_path / str(item_id) / "orig.jpg")

    pipeline_result = _mock_pipeline_result(
        primary="Brown",
        secondary="Tan",
        color_conf=0.74,
        secondary_conf=0.65,
        category="outerwear",
        category_conf=0.75,
        subcategory="coat",
        sub_conf=0.7,
        materials=[("wool", 0.72)],
        styles=[("outdoor", 0.7)],
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: pipeline_result)

    ai_tasks.classify_and_update_item(item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    # Category already set; should remain unchanged.
    assert refreshed.category == "top"
    # Subcategory should populate because it was missing.
    assert refreshed.subcategory == "coat"
    merged_tags = [tag.tag for tag in refreshed.tags]
    assert merged_tags == ["casual", "outdoor", "wool"]
    assert refreshed.primary_color == "Brown"
    assert refreshed.secondary_color == "Tan"
    assert refreshed.ai_confidence == pytest.approx(0.75)
    assert refreshed.color == "blue"


def test_classify_and_update_item_skips_deleted(db_session, tmp_path, monkeypatch):
    _prepare_settings(monkeypatch, tmp_path, session=db_session)
    item_id = uuid.uuid4()
    image_rel = f"/media/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="black",
        brand=None,
        image_url=image_rel,
        deleted_at=dt.datetime.now(dt.UTC),
    )
    db_session.add(item)
    db_session.commit()

    _create_local_image(tmp_path / str(item_id) / "orig.jpg")
    invoked = False

    def _unexpected_call(path: Path) -> PipelineResult:  # pragma: no cover
        nonlocal invoked
        invoked = True
        raise AssertionError("pipeline should not be invoked for deleted items")

    monkeypatch.setattr(ai_tasks.pipeline, "run", _unexpected_call)

    ai_tasks.classify_and_update_item(item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    assert refreshed.category == "unknown"
    # pipeline should never be invoked
    assert invoked is False
