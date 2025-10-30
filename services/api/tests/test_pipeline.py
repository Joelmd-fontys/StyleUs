from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
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
            "subcategory": "sneakers",
            "subcategory_confidence": 0.8,
            "materials": [("canvas", 0.85)],
            "styles": [("streetwear", 0.83)],
            "scores": {
                "category": {"shoes": 0.9},
                "subcategory": {"sneakers": 0.8},
                "materials": {"canvas": 0.85},
                "styles": {"streetwear": 0.83},
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
    assert result.clip["subcategory"] == "sneakers"
    assert result.clip["category_confidence"] >= 0.7
