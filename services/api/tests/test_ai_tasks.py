from __future__ import annotations

import datetime as dt
import io
import uuid
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.ai import color
from app.ai import tasks as ai_tasks
from app.ai.pipeline import PipelineResult
from app.api.deps import DEFAULT_USER_ID
from app.core.config import get_settings
from app.models.user import User
from app.models.wardrobe import ItemTag, WardrobeItem
from app.utils import storage as storage_utils


class FakeStorageAdapter:
    def __init__(self) -> None:
        self.objects: dict[str, storage_utils.DownloadedObject] = {}
        self.downloaded_paths: list[str] = []

    def download_object(self, object_path: str) -> storage_utils.DownloadedObject:
        self.downloaded_paths.append(object_path)
        if object_path not in self.objects:
            raise storage_utils.SupabaseStorageNotFoundError(object_path)
        return self.objects[object_path]


def _prepare_settings(
    monkeypatch: pytest.MonkeyPatch,
    media_root: Path,
    storage: FakeStorageAdapter,
    session=None,
    **env: str,
) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    ai_tasks.settings = get_settings()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: storage)
    if session is not None:
        monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: nullcontext(session))
        if session.get(User, DEFAULT_USER_ID) is None:
            session.add(User(id=DEFAULT_USER_ID, email="test@example.com"))
            session.commit()


def _create_image_bytes() -> bytes:
    image = Image.new("RGB", (128, 128), color=(220, 180, 120))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _mock_pipeline_result(
    *,
    primary: str,
    secondary: str | None,
    color_conf: float,
    secondary_conf: float | None,
    category: str,
    category_conf: float,
    materials: list[tuple[str, float]],
    style_tags: list[tuple[str, float]],
    attribute_tags: list[tuple[str, float]] | None = None,
    subcategory: str | None = None,
    subcategory_conf: float | None = None,
) -> PipelineResult:
    scores_category = {category: category_conf}
    score_materials = dict(materials)
    score_style_tags = dict(style_tags)
    score_attribute_tags = dict(attribute_tags or [])
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
            "materials": materials,
            "style_tags": style_tags,
            "attribute_tags": attribute_tags or [],
            "subcategory": subcategory,
            "subcategory_confidence": subcategory_conf,
            "scores": {
                "category": scores_category,
                "materials": score_materials,
                "style_tags": score_style_tags,
                "attribute_tags": score_attribute_tags,
                "subcategory": {subcategory: subcategory_conf} if subcategory else {},
            },
            "model_name": "stub-fashionclip",
        },
        cached=False,
        embedding=np.array([0.11, -0.22, 0.33], dtype=np.float32),
        embedding_model="stub-fashionclip",
    )


def test_classify_and_update_item_populates_empty_fields(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_settings(monkeypatch, tmp_path, storage, session=db_session)
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

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )

    pipeline_result = _mock_pipeline_result(
        primary="Camel",
        secondary="Tan",
        color_conf=0.82,
        secondary_conf=0.74,
        category="outerwear",
        category_conf=0.92,
        materials=[("leather", 0.88)],
        style_tags=[("heritage", 0.81)],
        attribute_tags=[("tailored", 0.74)],
        subcategory="coat",
        subcategory_conf=0.91,
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
    assert refreshed_tags == ["heritage", "leather", "tailored"]
    assert refreshed.ai_materials == ["leather"]
    assert refreshed.ai_style_tags == ["heritage"]
    assert refreshed.ai_attribute_tags == ["tailored"]
    assert refreshed.ai_embedding_model == "stub-fashionclip"
    assert refreshed.ai_embedding == [0.11, -0.22, 0.33]


def test_build_ai_preview_payload_preserves_full_prediction_set() -> None:
    payload = ai_tasks.build_ai_preview_payload(
        _mock_pipeline_result(
            primary="Camel",
            secondary="Tan",
            color_conf=0.82,
            secondary_conf=0.74,
            category="outerwear",
            category_conf=0.92,
            materials=[("leather", 0.88), ("wool", 0.81)],
            style_tags=[("heritage", 0.84), ("minimal", 0.77)],
            attribute_tags=[("tailored", 0.73)],
            subcategory="coat",
            subcategory_conf=0.91,
        )
    )

    assert payload["category"] == "outerwear"
    assert payload["subcategory"] == "coat"
    assert payload["primary_color"] == "Camel"
    assert payload["secondary_color"] == "Tan"
    assert payload["primary_color_confidence"] == pytest.approx(0.82)
    assert payload["secondary_color_confidence"] == pytest.approx(0.74)
    assert payload["materials"] == ["leather", "wool"]
    assert payload["style_tags"] == ["heritage", "minimal"]
    assert payload["attributes"] == ["tailored"]
    assert payload["tags"] == ["leather", "heritage", "wool"]
    assert payload["tag_confidences"] == {
        "leather": pytest.approx(0.88),
        "heritage": pytest.approx(0.84),
        "wool": pytest.approx(0.81),
    }
    assert payload["confidence"] == pytest.approx(0.92)
    assert payload["uncertain"] is False
    assert payload["uncertain_fields"] == []


def test_build_ai_preview_payload_only_flags_subcategory_when_category_meets_floor() -> None:
    payload = ai_tasks.build_ai_preview_payload(
        _mock_pipeline_result(
            primary="Black",
            secondary="Gray",
            color_conf=0.48,
            secondary_conf=0.52,
            category="top",
            category_conf=0.55,
            materials=[("canvas", 0.4)],
            style_tags=[("minimal", 0.43)],
            attribute_tags=[("relaxed", 0.44)],
            subcategory="polo",
            subcategory_conf=0.32,
        )
    )

    assert payload["category"] == "top"
    assert payload["category_confidence"] == pytest.approx(0.55)
    assert payload["subcategory"] is None
    assert payload["subcategory_confidence"] is None
    assert payload["primary_color"] is None
    assert payload["primary_color_confidence"] is None
    assert payload["secondary_color"] is None
    assert payload["secondary_color_confidence"] is None
    assert payload["materials"] == []
    assert payload["style_tags"] == []
    assert payload["attributes"] == []
    assert payload["tags"] == []
    assert payload["tag_confidences"] == {}
    assert payload["uncertain"] is True
    assert payload["uncertain_fields"] == ["subcategory"]


def test_build_ai_preview_payload_flags_mid_confidence_accessory_for_review() -> None:
    payload = ai_tasks.build_ai_preview_payload(
        _mock_pipeline_result(
            primary="Black",
            secondary=None,
            color_conf=0.82,
            secondary_conf=None,
            category="accessory",
            category_conf=0.59,
            materials=[("leather", 0.67)],
            style_tags=[("minimal", 0.63)],
            attribute_tags=[("tailored", 0.58)],
            subcategory="belt",
            subcategory_conf=0.89,
        )
    )

    assert payload["category"] == "accessory"
    assert payload["category_confidence"] == pytest.approx(0.59)
    assert payload["uncertain"] is True
    assert payload["uncertain_fields"] == ["category"]


def test_build_ai_preview_payload_flags_low_confidence_category_review() -> None:
    payload = ai_tasks.build_ai_preview_payload(
        _mock_pipeline_result(
            primary="Camel",
            secondary=None,
            color_conf=0.82,
            secondary_conf=None,
            category="accessory",
            category_conf=0.42,
            materials=[("leather", 0.67)],
            style_tags=[("minimal", 0.63)],
            attribute_tags=[("tailored", 0.58)],
            subcategory="belt",
            subcategory_conf=0.89,
        )
    )

    assert payload["category"] is None
    assert payload["category_confidence"] is None
    assert payload["subcategory"] is None
    assert payload["subcategory_confidence"] is None
    assert payload["uncertain"] is True
    assert payload["uncertain_fields"] == ["category"]


def test_classification_limits_tags_to_top_three(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_settings(monkeypatch, tmp_path, storage, session=db_session)
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

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )

    pipeline_result = _mock_pipeline_result(
        primary="Black",
        secondary=None,
        color_conf=0.9,
        secondary_conf=None,
        category="shoes",
        category_conf=0.93,
        materials=[("leather", 0.86), ("canvas", 0.81)],
        style_tags=[
            ("streetwear", 0.91),
            ("retro", 0.89),
            ("minimal", 0.88),
            ("heritage", 0.83),
        ],
        subcategory="sneakers",
        subcategory_conf=0.9,
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: pipeline_result)

    ai_tasks.classify_and_update_item(item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    saved_tags = [tag.tag for tag in refreshed.tags]
    assert set(saved_tags) == {"minimal", "retro", "streetwear"}
    assert len(saved_tags) == 3
    assert refreshed.ai_style_tags == ["streetwear", "retro", "minimal"]


def test_classify_and_update_item_respects_existing_data(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_settings(monkeypatch, tmp_path, storage, session=db_session)
    item_id = uuid.uuid4()
    object_path = f"users/{DEFAULT_USER_ID}/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="top",
        color="blue",
        brand="Acme",
        image_object_path=object_path,
    )
    item.tags.append(ItemTag(tag="casual"))
    db_session.add(item)
    db_session.commit()

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )

    pipeline_result = _mock_pipeline_result(
        primary="Brown",
        secondary="Tan",
        color_conf=0.74,
        secondary_conf=0.65,
        category="outerwear",
        category_conf=0.75,
        materials=[("wool", 0.72)],
        style_tags=[("outdoor", 0.7)],
        subcategory="coat",
        subcategory_conf=0.74,
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: pipeline_result)

    ai_tasks.classify_and_update_item(item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    # Category already set; should remain unchanged.
    assert refreshed.category == "top"
    assert refreshed.subcategory == "coat"
    merged_tags = [tag.tag for tag in refreshed.tags]
    assert merged_tags == ["casual", "outdoor", "wool"]
    assert refreshed.primary_color == "Brown"
    assert refreshed.secondary_color == "Tan"
    assert refreshed.ai_confidence == pytest.approx(0.75)
    assert refreshed.color == "blue"
    assert refreshed.ai_materials == ["wool"]
    assert refreshed.ai_style_tags == ["outdoor"]


def test_classify_and_update_item_skips_deleted(db_session, tmp_path, monkeypatch):
    storage = FakeStorageAdapter()
    _prepare_settings(monkeypatch, tmp_path, storage, session=db_session)
    item_id = uuid.uuid4()
    object_path = f"users/{DEFAULT_USER_ID}/{item_id}/orig.jpg"
    item = WardrobeItem(
        id=item_id,
        user_id=DEFAULT_USER_ID,
        category="unknown",
        color="black",
        brand=None,
        image_object_path=object_path,
        deleted_at=dt.datetime.now(dt.UTC),
    )
    db_session.add(item)
    db_session.commit()

    storage.objects[object_path] = storage_utils.DownloadedObject(
        object_path=object_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )
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


def test_run_item_enrichment_falls_back_to_original_when_medium_is_unavailable(
    db_session,
    tmp_path,
    monkeypatch,
):
    storage = FakeStorageAdapter()
    _prepare_settings(monkeypatch, tmp_path, storage, session=db_session)
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
        image_checksum="b" * 64,
    )
    db_session.add(item)
    db_session.commit()

    storage.objects[orig_path] = storage_utils.DownloadedObject(
        object_path=orig_path,
        data=_create_image_bytes(),
        content_type="image/jpeg",
        size=0,
    )

    pipeline_result = _mock_pipeline_result(
        primary="Camel",
        secondary="Tan",
        color_conf=0.82,
        secondary_conf=0.74,
        category="outerwear",
        category_conf=0.92,
        materials=[("leather", 0.88)],
        style_tags=[("heritage", 0.81)],
        subcategory="coat",
        subcategory_conf=0.91,
    )
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: pipeline_result)

    ai_tasks.run_item_enrichment(db_session, item_id)

    refreshed = db_session.get(WardrobeItem, item_id)
    assert refreshed is not None
    assert refreshed.category == "outerwear"
    assert storage.downloaded_paths == [medium_path, orig_path]
