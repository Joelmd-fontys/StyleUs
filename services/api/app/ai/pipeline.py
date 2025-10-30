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

_HEURISTIC_KEYWORDS: tuple[tuple[str, str, str | None, tuple[str, ...]], ...] = (
    ("sneaker", "shoes", "sneakers", ("streetwear", "sport")),
    ("runner", "shoes", "sneakers", ("athletic", "sport")),
    ("boot", "shoes", "boots", ("outdoor", "heritage")),
    ("loafer", "shoes", "loafers", ("smart-casual", "minimal")),
    ("heel", "shoes", "heels", ("luxury", "formal")),
    ("sand", "shoes", "sandals", ("summer", "casual")),
    ("jacket", "outerwear", "jacket", ("outdoor", "streetwear")),
    ("coat", "outerwear", "coat", ("formal", "luxury")),
    ("puffer", "outerwear", "puffer", ("outdoor", "warm")),
    ("hoodie", "top", "hoodie", ("streetwear", "casual")),
    ("sweater", "top", "sweater", ("minimal", "warm")),
    ("crew", "top", "sweater", ("minimal", "casual")),
    ("tshirt", "top", "t-shirt", ("casual", "minimal")),
    ("tee", "top", "t-shirt", ("casual", "minimal")),
    ("shirt", "top", "shirt", ("smart-casual", "formal")),
    ("blouse", "top", "blouse", ("formal", "minimal")),
    ("jean", "bottom", "jeans", ("denim", "casual")),
    ("chino", "bottom", "chinos", ("smart-casual", "minimal")),
    ("trouser", "bottom", "trousers", ("formal", "smart-casual")),
    ("pant", "bottom", "trousers", ("formal", "minimal")),
    ("short", "bottom", "shorts", ("summer", "casual")),
    ("skirt", "bottom", "skirt", ("minimal", "formal")),
    ("legging", "bottom", "leggings", ("athletic", "casual")),
    ("bag", "accessory", "bag", ("streetwear", "minimal")),
    ("belt", "accessory", "belt", ("heritage", "smart-casual")),
    ("cap", "accessory", "cap", ("streetwear", "athletic")),
    ("beanie", "accessory", "beanie", ("winter", "outdoor")),
    ("scarf", "accessory", "scarf", ("winter", "heritage")),
    ("watch", "accessory", "watch", ("luxury", "formal")),
    ("sunglass", "accessory", "sunglasses", ("retro", "summer")),
    ("glove", "accessory", "gloves", ("winter", "outdoor")),
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
    subcategory: str | None = None
    sub_conf: float | None = None
    tags: list[str] = []

    for keyword, cat, sub, extra_tags in _HEURISTIC_KEYWORDS:
        if keyword in filename:
            category = cat
            category_conf = 0.72
            subcategory = sub
            sub_conf = 0.68 if sub else None
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
        subcategory=subcategory,
        subcategory_confidence=sub_conf,
        materials=materials_list,
        styles=styles_list,
        scores={
            "category": {category: category_conf},
            "subcategory": {subcategory: sub_conf} if subcategory and sub_conf else {},
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
