from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app.ai import color, pipeline
from app.ai.pipeline import PipelineResult


class _StubPredictor:
    def __init__(self) -> None:
        self.calls = 0

    def embed_image(self, path: Path) -> np.ndarray:
        self.calls += 1
        return np.ones(512, dtype=np.float32)

    def predict(self, embedding: np.ndarray) -> dict[str, Any]:
        return {
            "category": "shoes",
            "category_confidence": 0.9,
            "materials": [("canvas", 0.85)],
            "style_tags": [("streetwear", 0.83)],
            "subcategory": "sneakers",
            "subcategory_confidence": 0.88,
            "scores": {
                "category": {"shoes": 0.9},
                "materials": {"canvas": 0.85},
                "style_tags": {"streetwear": 0.83},
                "subcategory": {"sneakers": 0.88},
            },
        }


def _stub_color_module(result: color.ColorResult) -> SimpleNamespace:
    return SimpleNamespace(get_colors_from_image=lambda _image: result)


def test_pipeline_caches_embedding(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(pipeline, "_EMB_CACHE_DIR", cache_dir)

    predictor = _StubPredictor()
    monkeypatch.setattr(pipeline, "_get_predictor", lambda: predictor)
    monkeypatch.setattr(
        pipeline,
        "_get_color_module",
        lambda: _stub_color_module(
            color.ColorResult(
                primary_color="Blue",
                secondary_color=None,
                confidence=0.9,
                secondary_confidence=None,
            )
        ),
    )

    image_path = tmp_path / "sample.png"
    Image.new("RGB", (128, 128), color=(30, 60, 200)).save(image_path)

    result_first: PipelineResult = pipeline.run(image_path)
    result_second: PipelineResult = pipeline.run(image_path)

    assert predictor.calls == 1
    assert result_first.cached is False
    assert result_second.cached is True


def test_pipeline_uses_full_image_for_classification_even_when_focus_mask_exists(
    tmp_path,
    monkeypatch,
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(pipeline, "_EMB_CACHE_DIR", cache_dir)

    class _RecordingPredictor(_StubPredictor):
        def __init__(self) -> None:
            super().__init__()
            self.embed_sizes: list[tuple[int, int]] = []

        def embed_pil_image(self, image: Image.Image) -> np.ndarray:
            self.calls += 1
            self.embed_sizes.append(image.size)
            return np.ones(512, dtype=np.float32)

    predictor = _RecordingPredictor()
    monkeypatch.setattr(pipeline, "_get_predictor", lambda: predictor)
    monkeypatch.setattr(
        pipeline,
        "_get_color_module",
        lambda: _stub_color_module(
            color.ColorResult(
                primary_color="Blue",
                secondary_color=None,
                confidence=0.9,
                secondary_confidence=None,
            )
        ),
    )

    image_path = tmp_path / "sample.png"
    Image.new("RGB", (128, 128), color=(30, 60, 200)).save(image_path)
    source_image = pipeline._load_source_image(image_path)
    monkeypatch.setattr(
        pipeline,
        "_prepare_focus_image",
        lambda _image: SimpleNamespace(
            image=source_image.crop((16, 16, 112, 112)),
            masked_image=Image.new("RGB", (48, 48), color=(255, 255, 255)),
            mask=np.ones((48, 48), dtype=bool),
            crop_box=(16, 16, 112, 112),
            method="grabcut",
            foreground_pixels=2304,
            foreground_ratio=0.14,
        ),
    )

    pipeline.run(image_path)

    assert predictor.embed_sizes == [(128, 128)]


def test_pipeline_uses_focus_image_when_classification_input_requests_it(
    tmp_path,
    monkeypatch,
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(pipeline, "_EMB_CACHE_DIR", cache_dir)
    monkeypatch.setattr(pipeline.settings, "ai_classification_input", "focus")

    class _RecordingPredictor(_StubPredictor):
        def __init__(self) -> None:
            super().__init__()
            self.embed_sizes: list[tuple[int, int]] = []

        def embed_pil_image(self, image: Image.Image) -> np.ndarray:
            self.calls += 1
            self.embed_sizes.append(image.size)
            return np.ones(512, dtype=np.float32)

    predictor = _RecordingPredictor()
    monkeypatch.setattr(pipeline, "_get_predictor", lambda: predictor)
    monkeypatch.setattr(
        pipeline,
        "_get_color_module",
        lambda: _stub_color_module(
            color.ColorResult(
                primary_color="Blue",
                secondary_color=None,
                confidence=0.9,
                secondary_confidence=None,
            )
        ),
    )

    image_path = tmp_path / "sample.png"
    Image.new("RGB", (128, 128), color=(30, 60, 200)).save(image_path)
    source_image = pipeline._load_source_image(image_path)
    monkeypatch.setattr(
        pipeline,
        "_prepare_focus_image",
        lambda _image: SimpleNamespace(
            image=source_image.crop((16, 16, 112, 112)),
            masked_image=Image.new("RGB", (48, 48), color=(255, 255, 255)),
            mask=np.ones((48, 48), dtype=bool),
            crop_box=(16, 16, 112, 112),
            method="grabcut",
            foreground_pixels=2304,
            foreground_ratio=0.14,
        ),
    )

    result = pipeline.run(image_path)

    assert predictor.embed_sizes == [(96, 96)]
    assert result.classification_input == "focus"


def test_pipeline_fallback_on_predictor_error(tmp_path, monkeypatch):
    image_path = tmp_path / "sneaker_sample.jpg"
    Image.new("RGB", (128, 128), color=(120, 80, 40)).save(image_path)

    monkeypatch.setattr(
        pipeline,
        "_get_color_module",
        lambda: _stub_color_module(
            color.ColorResult(
                primary_color="Camel",
                secondary_color=None,
                confidence=0.9,
                secondary_confidence=None,
            )
        ),
    )

    def _raise():
        raise RuntimeError("clip unavailable")

    monkeypatch.setattr(pipeline, "_get_predictor", _raise)

    result = pipeline.run(image_path)

    assert result.cached is False
    assert result.clip["category"] == "shoes"
    assert result.clip["category_confidence"] >= 0.7


def test_subcategory_selection_prefers_highest_score(tmp_path, monkeypatch):
    clip = {
        "category": "top",
        "category_confidence": 0.82,
        "subcategory": None,
        "subcategory_confidence": None,
        "materials": [],
        "style_tags": [],
        "scores": {
            "subcategory": {"hoodie": 0.75, "t-shirt": 0.6},
        },
    }
    image_path = tmp_path / "hoodie.png"
    image_path.write_text("stub")
    colors = color.ColorResult(
        primary_color="Black",
        secondary_color=None,
        confidence=0.9,
        secondary_confidence=None,
    )
    monkeypatch.setattr(pipeline.settings, "ai_subcategory_confidence_threshold", 0.5)

    label, confidence = pipeline._select_subcategory(
        clip=clip,
        image_path=image_path,
        colors=colors,
    )

    assert label == "hoodie"
    assert confidence == pytest.approx(0.75)


def test_subcategory_selection_falls_back_to_keywords(tmp_path, monkeypatch):
    clip = {
        "category": "shoes",
        "category_confidence": 0.6,
        "subcategory": "boots",
        "subcategory_confidence": 0.3,
        "materials": [],
        "style_tags": [],
        "scores": {
            "subcategory": {"boots": 0.3},
        },
    }
    image_path = tmp_path / "fresh-sneaker.jpg"
    image_path.write_text("stub")
    colors = color.ColorResult(
        primary_color=None,
        secondary_color=None,
        confidence=0.0,
        secondary_confidence=None,
    )
    monkeypatch.setattr(pipeline.settings, "ai_subcategory_confidence_threshold", 0.6)

    label, confidence = pipeline._select_subcategory(
        clip=clip,
        image_path=image_path,
        colors=colors,
    )

    assert label == "sneakers"
    assert confidence >= pipeline.settings.ai_subcategory_confidence_threshold
