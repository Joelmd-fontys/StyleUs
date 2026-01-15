"""Embedding pipeline coordinating color extraction and CLIP heads."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.ai import color
from app.ai.clip_heads import ClipPrediction, get_predictor
from app.ai.labels import MATERIAL_LABELS, STYLE_LABELS
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.pipeline")

_EMB_CACHE_DIR = settings.media_root_path / ".emb_cache"
_EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_SUBCATEGORY_FALLBACK_CONFIDENCE = 0.55


@dataclass(frozen=True, slots=True)
class KeywordHint:
    keyword: str
    category: str
    subcategory: str | None
    materials: tuple[str, ...]
    style_tags: tuple[str, ...]


_HEURISTIC_KEYWORDS: tuple[KeywordHint, ...] = (
    KeywordHint("sneaker", "shoes", "sneakers", ("mesh", "leather"), ("streetwear", "sport")),
    KeywordHint("runner", "shoes", "sneakers", ("mesh",), ("sport",)),
    KeywordHint("boot", "shoes", "boots", ("leather", "suede"), ("outdoor",)),
    KeywordHint("loafer", "shoes", "loafers", ("leather",), ("formal", "minimal")),
    KeywordHint("heel", "shoes", "heels", ("leather",), ("formal",)),
    KeywordHint("sandal", "shoes", "sandals", ("mesh", "leather"), ("minimal", "retro")),
    KeywordHint("jacket", "top", "jacket", ("nylon",), ("outdoor", "streetwear")),
    KeywordHint("coat", "top", "coat", ("wool", "leather"), ("formal",)),
    KeywordHint("puffer", "outerwear", "puffer", ("nylon", "fleece"), ("outdoor",)),
    KeywordHint("windbreaker", "outerwear", "windbreaker", ("nylon",), ("sport", "outdoor")),
    KeywordHint("rain", "outerwear", "rain jacket", ("nylon",), ("outdoor",)),
    KeywordHint("fleece", "outerwear", "fleece", ("fleece",), ("outdoor", "minimal")),
    KeywordHint("hoodie", "top", "hoodie", ("knit", "fleece"), ("streetwear", "sport")),
    KeywordHint("sweatshirt", "top", "sweatshirt", ("knit",), ("streetwear", "minimal")),
    KeywordHint("sweater", "top", "sweater", ("wool", "knit"), ("minimal", "retro")),
    KeywordHint("crew", "top", "long sleeve", ("cotton",), ("minimal", "retro")),
    KeywordHint("tshirt", "top", "t-shirt", ("cotton",), ("minimal", "streetwear")),
    KeywordHint("tee", "top", "t-shirt", ("cotton",), ("minimal", "streetwear")),
    KeywordHint("tank", "top", "tank top", ("cotton", "mesh"), ("sport", "minimal")),
    KeywordHint("shirt", "top", "shirt", ("cotton",), ("formal", "minimal")),
    KeywordHint("polo", "top", "polo", ("cotton",), ("sport", "minimal")),
    KeywordHint("longsleeve", "top", "long sleeve", ("cotton",), ("minimal", "retro")),
    KeywordHint("jean", "bottom", "jeans", ("denim",), ("retro", "streetwear")),
    KeywordHint("denim", "bottom", "jeans", ("denim",), ("retro", "streetwear")),
    KeywordHint("chino", "bottom", "chinos", ("cotton",), ("minimal", "formal")),
    KeywordHint("trouser", "bottom", "trousers", ("wool", "cotton"), ("formal",)),
    KeywordHint("pant", "bottom", "trousers", ("cotton",), ("formal", "minimal")),
    KeywordHint("short", "bottom", "shorts", ("cotton",), ("sport", "retro")),
    KeywordHint("skirt", "bottom", "skirt", ("cotton", "denim"), ("minimal", "retro")),
    KeywordHint("sneak", "shoes", "sneakers", ("mesh",), ("sport", "streetwear")),
    KeywordHint("bag", "accessory", "bag", ("leather", "canvas"), ("streetwear", "minimal")),
    KeywordHint("belt", "accessory", "belt", ("leather",), ("formal", "retro")),
    KeywordHint("cap", "accessory", "cap", ("mesh", "cotton"), ("sport", "streetwear")),
    KeywordHint("beanie", "accessory", "beanie", ("knit", "fleece"), ("outdoor",)),
    KeywordHint("scarf", "accessory", "scarf", ("wool", "knit"), ("retro", "formal")),
    KeywordHint("watch", "accessory", "watch", ("leather",), ("formal", "minimal")),
    KeywordHint("sunglass", "accessory", "sunglasses", (), ("retro", "minimal")),
    KeywordHint("goggle", "accessory", "sunglasses", (), ("sport", "outdoor")),
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


def _normalize_token(value: str | None) -> str:
    return value.lower().strip() if value else ""


def _match_keyword(keyword_source: str, *, category: str | None = None) -> KeywordHint | None:
    for hint in _HEURISTIC_KEYWORDS:
        if hint.keyword in keyword_source and (category is None or hint.category == category):
            return hint
    return None


def _find_keyword_hint(
    *,
    category: str | None,
    image_path: Path,
    colors: color.ColorResult,
) -> KeywordHint | None:
    candidates = [
        image_path.name.lower(),
        image_path.stem.lower(),
        _normalize_token(colors.primary_color),
        _normalize_token(colors.secondary_color),
    ]
    for value in candidates:
        if not value:
            continue
        hint = _match_keyword(value, category=category)
        if hint:
            return hint
    return None


def _select_subcategory(
    *,
    clip: ClipPrediction,
    image_path: Path,
    colors: color.ColorResult,
) -> tuple[str | None, float | None]:
    scores = (clip.get("scores") or {}).get("subcategory", {}) or {}
    candidate = clip.get("subcategory")
    candidate_conf = clip.get("subcategory_confidence") or (
        scores.get(candidate) if candidate else None
    )

    if not candidate and scores:
        candidate, candidate_conf = max(scores.items(), key=lambda item: item[1])

    if candidate and candidate_conf is not None:
        if candidate_conf >= settings.ai_subcategory_confidence_threshold:
            return candidate, candidate_conf

    hint = _find_keyword_hint(category=clip["category"], image_path=image_path, colors=colors)
    if hint and hint.subcategory:
        return (
            hint.subcategory,
            max(settings.ai_subcategory_confidence_threshold, _SUBCATEGORY_FALLBACK_CONFIDENCE),
        )

    if candidate:
        return candidate, candidate_conf
    return None, None


def _apply_subcategory_selection(
    clip: ClipPrediction,
    *,
    image_path: Path,
    colors: color.ColorResult,
) -> None:
    selected, confidence = _select_subcategory(clip=clip, image_path=image_path, colors=colors)
    clip["subcategory"] = selected
    clip["subcategory_confidence"] = confidence
    scores = clip.setdefault("scores", {})
    sub_scores = dict(scores.get("subcategory") or {})
    if selected and confidence is not None:
        sub_scores[selected] = confidence
    scores["subcategory"] = sub_scores


def _score_list(labels: tuple[str, ...], *, base: float) -> list[tuple[str, float]]:
    seen: set[str] = set()
    results: list[tuple[str, float]] = []
    for label in labels:
        normalized = _normalize_token(label)
        if not normalized or normalized in seen:
            continue
        if normalized not in MATERIAL_LABELS and normalized not in STYLE_LABELS:
            continue
        seen.add(normalized)
        results.append((normalized, base))
    return results


def _heuristic_prediction(image_path: Path, colors: color.ColorResult) -> ClipPrediction:
    hint = _find_keyword_hint(category=None, image_path=image_path, colors=colors)
    category = hint.category if hint else "accessory"
    subcategory = hint.subcategory if hint else None
    category_conf = 0.72 if hint else 0.45
    subcategory_conf = 0.6 if subcategory else None

    material_labels: list[tuple[str, float]] = []
    style_labels: list[tuple[str, float]] = []
    if hint:
        material_labels.extend(_score_list(hint.materials, base=0.7))
        style_labels.extend(_score_list(hint.style_tags, base=0.68))

    material_scores = dict(material_labels)
    style_scores = dict(style_labels)
    sub_scores: dict[str, float] = {}
    if subcategory and subcategory_conf is not None:
        sub_scores[subcategory] = subcategory_conf

    return ClipPrediction(
        category=category,
        category_confidence=category_conf,
        materials=material_labels,
        style_tags=style_labels,
        subcategory=subcategory,
        subcategory_confidence=subcategory_conf,
        scores={
            "category": {category: category_conf},
            "materials": material_scores,
            "style_tags": style_scores,
            "subcategory": sub_scores,
        },
    )


def run(image_path: Path) -> PipelineResult:
    color_result = color.get_colors(str(image_path))
    cached = False
    try:
        predictor = get_predictor()
        embedding, cached = _load_embedding(image_path, predictor)
        clip_result = predictor.predict(embedding)
        _apply_subcategory_selection(
            clip_result,
            image_path=image_path,
            colors=color_result,
        )
        LOGGER.debug(
            "ai.pipeline.prediction",
            extra={
                "category": clip_result.get("category"),
                "category_confidence": clip_result.get("category_confidence"),
                "subcategory": clip_result.get("subcategory"),
                "subcategory_confidence": clip_result.get("subcategory_confidence"),
                "materials": clip_result.get("materials", [])[:3],
                "style_tags": clip_result.get("style_tags", [])[:3],
            },
        )
    except RuntimeError as exc:
        LOGGER.warning("ai.pipeline.predictor_unavailable", extra={"error": str(exc)})
        clip_result = _heuristic_prediction(image_path, color_result)
        cached = False
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("ai.pipeline.clip_failed", extra={"error": str(exc)})
        clip_result = _heuristic_prediction(image_path, color_result)
        cached = False
    return PipelineResult(colors=color_result, clip=clip_result, cached=cached)
