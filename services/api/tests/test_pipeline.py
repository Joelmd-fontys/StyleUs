from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app.ai import pipeline
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


def test_pipeline_caches_embedding(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(pipeline, "_EMB_CACHE_DIR", cache_dir)

    predictor = _StubPredictor()
    monkeypatch.setattr(pipeline, "get_predictor", lambda: predictor)

    monkeypatch.setattr(
        pipeline.color,
        "get_colors",
        lambda path: pipeline.color.ColorResult(
            primary_color="Blue",
            secondary_color=None,
            confidence=0.9,
            secondary_confidence=None,
        ),
    )

    image_path = tmp_path / "sample.png"
    Image.new("RGB", (128, 128), color=(30, 60, 200)).save(image_path)

    result_first: PipelineResult = pipeline.run(image_path)
    result_second: PipelineResult = pipeline.run(image_path)

    assert predictor.calls == 1
    assert result_first.cached is False
    assert result_second.cached is True


def test_pipeline_fallback_on_predictor_error(tmp_path, monkeypatch):
    image_path = tmp_path / "sneaker_sample.jpg"
    Image.new("RGB", (128, 128), color=(120, 80, 40)).save(image_path)

    monkeypatch.setattr(
        pipeline.color,
        "get_colors",
        lambda path: pipeline.color.ColorResult(
            primary_color="Camel",
            secondary_color=None,
            confidence=0.9,
            secondary_confidence=None,
        ),
    )

    def _raise():
        raise RuntimeError("clip unavailable")

    monkeypatch.setattr(pipeline, "get_predictor", _raise)

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
    colors = pipeline.color.ColorResult(
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
    colors = pipeline.color.ColorResult(
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
