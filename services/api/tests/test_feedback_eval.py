from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from app.ai import color, feedback_eval
from app.ai.pipeline import PipelineResult
from app.api.deps import DEFAULT_USER_ID
from app.models.ai_feedback import AIReviewFeedbackEvent
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.utils import storage as storage_utils

_SAMPLE_IMAGE_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "sample_images"
_FEEDBACK_FIXTURE_MANIFEST = (
    Path(__file__).resolve().parent / "fixtures" / "upload_review_feedback_cases.yaml"
)


class FakeStorageAdapter:
    def __init__(self) -> None:
        self.objects: dict[str, storage_utils.DownloadedObject] = {}

    def download_object(self, object_path: str) -> storage_utils.DownloadedObject:
        try:
            return self.objects[object_path]
        except KeyError as exc:  # pragma: no cover - defensive
            raise storage_utils.SupabaseStorageNotFoundError(object_path) from exc


def _sample_bytes(file_name: str) -> bytes:
    return (_SAMPLE_IMAGE_DIR / file_name).read_bytes()


def _stub_pipeline_result(*, category_label: str, confidence: float) -> PipelineResult:
    return PipelineResult(
        colors=color.ColorResult(
            primary_color="Black",
            secondary_color=None,
            confidence=0.8,
            secondary_confidence=None,
        ),
        clip={
            "category": category_label,
            "category_confidence": confidence,
            "materials": [],
            "style_tags": [],
            "attribute_tags": [],
            "subcategory": None,
            "subcategory_confidence": None,
            "scores": {"category": {category_label: confidence}},
            "model_name": "stub-fashionclip",
        },
        cached=False,
    )


def test_export_review_feedback_eval_slice_writes_latest_feedback_images(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda _settings: storage)

    user = User(id=DEFAULT_USER_ID, email="user@example.com")
    db_session.add(user)

    belt_item = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="accessory",
        subcategory="belt",
        color="black",
        image_medium_object_path="users/demo/belt.png",
    )
    cap_item = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="accessory",
        subcategory="cap",
        color="black",
        image_medium_object_path="users/demo/cap.png",
    )
    db_session.add_all([belt_item, cap_item])
    db_session.flush()

    storage.objects["users/demo/belt.png"] = storage_utils.DownloadedObject(
        object_path="users/demo/belt.png",
        data=_sample_bytes("zara.png"),
        content_type="image/png",
        size=None,
    )
    storage.objects["users/demo/cap.png"] = storage_utils.DownloadedObject(
        object_path="users/demo/cap.png",
        data=_sample_bytes("hm.png"),
        content_type="image/png",
        size=None,
    )

    db_session.add_all(
        [
            AIReviewFeedbackEvent(
                item_id=belt_item.id,
                user_id=DEFAULT_USER_ID,
                predicted_category="top",
                corrected_category="accessory",
                prediction_confidence=0.56,
                accepted_directly=False,
                source="upload_review",
            ),
            AIReviewFeedbackEvent(
                item_id=belt_item.id,
                user_id=DEFAULT_USER_ID,
                predicted_category="bottom",
                corrected_category="accessory",
                prediction_confidence=0.58,
                accepted_directly=False,
                source="upload_review",
            ),
            AIReviewFeedbackEvent(
                item_id=cap_item.id,
                user_id=DEFAULT_USER_ID,
                predicted_category="accessory",
                corrected_category="accessory",
                prediction_confidence=0.77,
                accepted_directly=True,
                source="upload_review",
            ),
        ]
    )
    db_session.commit()

    manifest_path = feedback_eval.export_review_feedback_eval_slice(
        db_session,
        output_dir=tmp_path / "eval",
        limit=10,
    )

    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert len(cases) == 2
    assert {case["historical_predicted_category"] for case in cases} == {"bottom", "accessory"}
    for case in cases:
        assert (manifest_path.parent / case["image"]).exists()


def test_build_review_feedback_report_groups_confusion_and_recommends_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_predictions = {
        "nike.png": _stub_pipeline_result(category_label="top", confidence=0.95),
        "adidas.png": _stub_pipeline_result(category_label="top", confidence=0.97),
        "levis.png": _stub_pipeline_result(category_label="bottom", confidence=0.93),
        "uniqlo.png": _stub_pipeline_result(category_label="bottom", confidence=0.92),
        "hm.png": _stub_pipeline_result(category_label="accessory", confidence=0.76),
        "zara.png": _stub_pipeline_result(category_label="accessory", confidence=0.67),
        "thenorthface.png": _stub_pipeline_result(category_label="outerwear", confidence=0.98),
        "converse.png": _stub_pipeline_result(category_label="shoes", confidence=0.99),
    }

    monkeypatch.setattr(
        feedback_eval.pipeline,
        "run",
        lambda image_path: current_predictions[Path(image_path).name],
    )

    cases = feedback_eval.load_review_feedback_cases(_FEEDBACK_FIXTURE_MANIFEST)
    report = feedback_eval.build_review_feedback_report(cases, target_precision=0.8)

    assert report.total_cases == 8
    assert report.historical_accuracy == pytest.approx(0.5)
    assert report.current_accuracy == pytest.approx(1.0)
    assert report.historical_confusion[0].predicted_category == "accessory"
    assert report.historical_confusion[0].expected_category == "top"
    assert report.historical_confusion[0].count == 2
    assert report.historical_confusion[1].predicted_category == "accessory"
    assert report.historical_confusion[1].expected_category == "bottom"
    assert report.historical_confusion[1].count == 2
    assert report.current_confusion == ()
    assert report.recommended_category_thresholds[0].category == "accessory"
    assert report.recommended_category_thresholds[0].threshold == pytest.approx(0.62)
    assert report.current_bands[0].band == "0.65-0.74"
    assert report.current_bands[0].accuracy == pytest.approx(1.0)
