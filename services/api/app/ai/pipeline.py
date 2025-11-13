"""Embedding pipeline coordinating color extraction and CLIP heads."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.ai import color
from app.ai.clip_heads import (
    MATERIALS,
    STYLES,
    ClipPrediction,
    get_predictor,
)
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.pipeline")

_EMB_CACHE_DIR = settings.media_root_path / ".emb_cache"
_EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_HEURISTIC_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("sneaker", "shoes", ("streetwear", "sport")),
    ("runner", "shoes", ("athletic", "sport")),
    ("boot", "shoes", ("outdoor", "heritage")),
    ("loafer", "shoes", ("smart-casual", "minimal")),
    ("heel", "shoes", ("luxury", "formal")),
    ("sand", "shoes", ("summer", "casual")),
    ("jacket", "outerwear", ("outdoor", "streetwear")),
    ("coat", "outerwear", ("formal", "luxury")),
    ("puffer", "outerwear", ("outdoor", "warm")),
    ("hoodie", "top", ("streetwear", "casual")),
    ("sweater", "top", ("minimal", "warm")),
    ("crew", "top", ("minimal", "casual")),
    ("tshirt", "top", ("casual", "minimal")),
    ("tee", "top", ("casual", "minimal")),
    ("shirt", "top", ("smart-casual", "formal")),
    ("blouse", "top", ("formal", "minimal")),
    ("jean", "bottom", ("denim", "casual")),
    ("chino", "bottom", ("smart-casual", "minimal")),
    ("trouser", "bottom", ("formal", "smart-casual")),
    ("pant", "bottom", ("formal", "minimal")),
    ("short", "bottom", ("summer", "casual")),
    ("skirt", "bottom", ("minimal", "formal")),
    ("legging", "bottom", ("athletic", "casual")),
    ("bag", "accessory", ("streetwear", "minimal")),
    ("belt", "accessory", ("heritage", "smart-casual")),
    ("cap", "accessory", ("streetwear", "athletic")),
    ("beanie", "accessory", ("winter", "outdoor")),
    ("scarf", "accessory", ("winter", "heritage")),
    ("watch", "accessory", ("luxury", "formal")),
    ("sunglass", "accessory", ("retro", "summer")),
    ("glove", "accessory", ("winter", "outdoor")),
)


@dataclass(slots=True)
class PipelineResult:
    colors: color.ColorResult
    clip: ClipPrediction
    cached: bool


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_embedding(image_path: Path, predictor: Any) -> tuple[np.ndarray, bool]:
    file_hash = _hash_file(image_path)
    cache_path = _EMB_CACHE_DIR / f"{file_hash}.npy"

    if cache_path.exists():
        try:
            embedding = np.load(cache_path)
            return embedding, True
        except Exception:  # pragma: no cover - corrupted cache
            LOGGER.warning("ai.pipeline.cache_corrupt", extra={"path": str(cache_path)})

    embedding = predictor.embed_image(image_path)
    try:
        np.save(cache_path, embedding)
    except Exception:  # pragma: no cover - filesystem issues
        LOGGER.warning("ai.pipeline.cache_write_failed", extra={"path": str(cache_path)})
    return embedding, False


def _heuristic_prediction(image_path: Path, colors: color.ColorResult) -> ClipPrediction:
    filename = image_path.name.lower()
    category = "accessory"
    category_conf = 0.45
    tags: list[str] = []

    for keyword, cat, extra_tags in _HEURISTIC_KEYWORDS:
        if keyword in filename:
            category = cat
            category_conf = 0.72
            tags.extend(extra_tags)
            break

    if colors.primary_color:
        primary_tag = colors.primary_color.lower()
        if primary_tag not in tags:
            tags.append(primary_tag)

    unique_tags: list[str] = []
    for tag in tags:
        normalized = tag.strip().lower()
        if normalized and normalized not in unique_tags:
            unique_tags.append(normalized)

    materials_list: list[tuple[str, float]] = []
    styles_list: list[tuple[str, float]] = []
    for tag in unique_tags:
        if tag in MATERIALS:
            materials_list.append((tag, 0.68))
        elif tag in STYLES:
            styles_list.append((tag, 0.65))
        else:
            styles_list.append((tag, 0.6))

    return ClipPrediction(
        category=category,
        category_confidence=category_conf,
        materials=materials_list,
        styles=styles_list,
        scores={
            "category": {category: category_conf},
            "materials": dict(materials_list),
            "styles": dict(styles_list),
        },
    )


def run(image_path: Path) -> PipelineResult:
    color_result = color.get_colors(str(image_path))
    cached = False
    try:
        predictor = get_predictor()
        embedding, cached = _load_embedding(image_path, predictor)
        clip_result = predictor.predict(embedding)
    except RuntimeError as exc:
        LOGGER.warning("ai.pipeline.predictor_unavailable", extra={"error": str(exc)})
        clip_result = _heuristic_prediction(image_path, color_result)
        cached = False
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("ai.pipeline.clip_failed", extra={"error": str(exc)})
        clip_result = _heuristic_prediction(image_path, color_result)
        cached = False
    return PipelineResult(colors=color_result, clip=clip_result, cached=cached)
