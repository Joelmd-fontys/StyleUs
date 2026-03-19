"""Embedding pipeline coordinating preprocessing, color extraction, and CLIP heads."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from PIL import Image, ImageOps

from app.ai.labels import ATTRIBUTE_LABELS, MATERIAL_LABELS, STYLE_LABELS
from app.ai.segmentation import GarmentFocus, has_opencv, prepare_garment_focus
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.pipeline")

_EMB_CACHE_DIR = settings.media_root_path / ".emb_cache"
_EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_PIPELINE_CACHE_VERSION = "fashion-v2"
_SUBCATEGORY_FALLBACK_CONFIDENCE = 0.55
_PRECOMPUTED_CACHE_KEY_PATTERN = re.compile(r"^(?P<cache_key>[0-9a-f]{64})(?:[_-].+)?$")

if TYPE_CHECKING:
    from app.ai import color
    from app.ai.clip_heads import ClipPrediction


@dataclass(frozen=True, slots=True)
class KeywordHint:
    keyword: str
    category: str
    subcategory: str | None
    materials: tuple[str, ...]
    style_tags: tuple[str, ...]
    attribute_tags: tuple[str, ...]


_HEURISTIC_KEYWORDS: tuple[KeywordHint, ...] = (
    KeywordHint(
        "sneaker",
        "shoes",
        "sneakers",
        ("mesh", "leather"),
        ("streetwear", "sporty"),
        ("chunky",),
    ),
    KeywordHint("runner", "shoes", "sneakers", ("mesh",), ("sporty",), ("chunky",)),
    KeywordHint("boot", "shoes", "boots", ("leather", "suede"), ("outdoor",), ("chunky",)),
    KeywordHint("loafer", "shoes", "loafers", ("leather",), ("formal",), ("tailored",)),
    KeywordHint("heel", "shoes", "heels", ("leather",), ("formal",), ("tailored",)),
    KeywordHint("sandal", "shoes", "sandals", ("mesh", "leather"), ("minimal",), ()),
    KeywordHint("jacket", "top", "jacket", ("nylon",), ("casual", "streetwear"), ("boxy",)),
    KeywordHint("coat", "top", "coat", ("wool", "leather"), ("formal", "heritage"), ("tailored",)),
    KeywordHint("puffer", "outerwear", "puffer", ("nylon",), ("outdoor",), ("quilted",)),
    KeywordHint(
        "windbreaker",
        "outerwear",
        "windbreaker",
        ("nylon",),
        ("sporty", "outdoor"),
        ("relaxed",),
    ),
    KeywordHint("rain", "outerwear", "rain jacket", ("nylon",), ("outdoor",), ()),
    KeywordHint("fleece", "outerwear", "fleece", ("fleece",), ("outdoor",), ("relaxed",)),
    KeywordHint("hoodie", "top", "hoodie", ("knit", "fleece"), ("streetwear",), ("oversized",)),
    KeywordHint(
        "sweatshirt",
        "top",
        "sweatshirt",
        ("knit",),
        ("casual", "streetwear"),
        ("relaxed",),
    ),
    KeywordHint("sweater", "top", "sweater", ("wool", "knit"), ("minimal", "heritage"), ()),
    KeywordHint("crew", "top", "long sleeve", ("cotton",), ("casual",), ("relaxed",)),
    KeywordHint("tshirt", "top", "t-shirt", ("cotton",), ("casual",), ("relaxed",)),
    KeywordHint("tee", "top", "t-shirt", ("cotton",), ("casual",), ("relaxed",)),
    KeywordHint("tank", "top", "tank top", ("cotton", "mesh"), ("sporty",), ("slim-fit",)),
    KeywordHint("shirt", "top", "shirt", ("cotton",), ("formal",), ("tailored",)),
    KeywordHint("polo", "top", "polo", ("cotton",), ("casual", "heritage"), ("slim-fit",)),
    KeywordHint("longsleeve", "top", "long sleeve", ("cotton",), ("casual",), ("relaxed",)),
    KeywordHint("jean", "bottom", "jeans", ("denim",), ("casual", "retro"), ()),
    KeywordHint("denim", "bottom", "jeans", ("denim",), ("casual", "retro"), ()),
    KeywordHint("chino", "bottom", "chinos", ("cotton",), ("minimal", "formal"), ("tailored",)),
    KeywordHint("trouser", "bottom", "trousers", ("wool", "cotton"), ("formal",), ("tailored",)),
    KeywordHint("pant", "bottom", "trousers", ("cotton",), ("formal",), ("tailored",)),
    KeywordHint("short", "bottom", "shorts", ("cotton",), ("casual", "sporty"), ("relaxed",)),
    KeywordHint("skirt", "bottom", "skirt", ("cotton", "denim"), ("minimal",), ("tailored",)),
    KeywordHint("bag", "accessory", "bag", ("leather", "canvas"), ("streetwear",), ()),
    KeywordHint("belt", "accessory", "belt", ("leather",), ("formal",), ("tailored",)),
    KeywordHint("cap", "accessory", "cap", ("cotton", "mesh"), ("sporty", "streetwear"), ()),
    KeywordHint("beanie", "accessory", "beanie", ("knit", "fleece"), ("outdoor",), ()),
    KeywordHint("scarf", "accessory", "scarf", ("wool", "knit"), ("heritage",), ()),
    KeywordHint("watch", "accessory", "watch", ("leather",), ("formal",), ("tailored",)),
    KeywordHint("sunglass", "accessory", "sunglasses", (), ("minimal",), ()),
)


@dataclass(slots=True)
class PipelineResult:
    colors: color.ColorResult
    clip: ClipPrediction
    cached: bool
    embedding: np.ndarray | None = None
    embedding_model: str | None = None
    preprocessing_duration_ms: float = 0.0
    color_duration_ms: float = 0.0
    embedding_duration_ms: float = 0.0
    prediction_duration_ms: float = 0.0
    inference_duration_ms: float = 0.0
    foreground_ratio: float = 0.0
    preprocessing_method: str | None = None


def _get_color_module() -> Any:
    from app.ai import color as color_module

    return color_module


def _get_predictor() -> Any:
    from app.ai.clip_heads import get_predictor

    return get_predictor()


def _get_color_result(focus: GarmentFocus) -> Any:
    color_module = _get_color_module()
    try:
        return color_module.get_colors_from_image(
            focus.image,
            mask=focus.mask,
            use_mask=False,
        )
    except TypeError:
        # Backward-compatible path for tests or callers still stubbing the older signature.
        return color_module.get_colors_from_image(focus.image)


def _hash_file(path: Path) -> str:
    match = _PRECOMPUTED_CACHE_KEY_PATTERN.match(path.stem.lower())
    if match:
        return match.group("cache_key")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _embedding_cache_path(image_path: Path, predictor: Any) -> Path:
    file_hash = _hash_file(image_path)
    predictor_key = getattr(predictor, "cache_key", "default")
    digest = hashlib.sha256(
        f"{file_hash}:{predictor_key}:{_PIPELINE_CACHE_VERSION}".encode()
    ).hexdigest()
    return _EMB_CACHE_DIR / f"{digest}.npy"


def _load_embedding(
    image_path: Path,
    predictor: Any,
    *,
    image: Image.Image,
) -> tuple[np.ndarray, bool]:
    cache_path = _embedding_cache_path(image_path, predictor)

    if cache_path.exists():
        try:
            embedding = np.load(cache_path)
            return embedding.astype(np.float32), True
        except Exception:  # pragma: no cover - corrupted cache
            LOGGER.warning("ai.pipeline.cache_corrupt", extra={"path": str(cache_path)})

    if hasattr(predictor, "embed_pil_image"):
        embedding = predictor.embed_pil_image(image)
    else:
        embedding = predictor.embed_image(image_path)
    try:
        np.save(cache_path, embedding.astype(np.float32))
    except Exception:  # pragma: no cover - filesystem issues
        LOGGER.warning("ai.pipeline.cache_write_failed", extra={"path": str(cache_path)})
    return embedding, False


def warm_up() -> bool:
    """Warm predictor state once at worker startup."""

    if not settings.ai_enable_classifier:
        LOGGER.info("ai.pipeline.warmup_skipped", extra={"mode": "heuristic_only"})
        return False

    started = time.perf_counter()
    try:
        _get_predictor()
    except RuntimeError as exc:
        LOGGER.warning(
            "ai.pipeline.warmup_unavailable",
            extra={
                "error": str(exc),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return False
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception(
            "ai.pipeline.warmup_failed",
            extra={
                "error": str(exc),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return False
    LOGGER.info(
        "ai.pipeline.warmup_completed",
        extra={"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )
    return True


def _load_source_image(image_path: Path) -> Image.Image:
    with Image.open(image_path) as image:
        transposed = ImageOps.exif_transpose(image)
        return cast(Image.Image, transposed.convert("RGB").copy())


def _select_mask_method() -> str:
    method = settings.ai_color_mask_method
    if method not in {"grabcut", "heuristic"}:
        method = "grabcut"
    if method == "grabcut" and not has_opencv():
        LOGGER.info("ai.pipeline.opencv_missing_fallback", extra={"fallback": "heuristic"})
        return "heuristic"
    return method


def _prepare_focus_image(source_image: Image.Image) -> GarmentFocus:
    method = cast("str", _select_mask_method())
    focus = prepare_garment_focus(source_image, method=cast("Any", method))
    LOGGER.info(
        "ai.pipeline.preprocessing",
        extra={
            "method": focus.method or "none",
            "crop_box": list(focus.crop_box),
            "foreground_pixels": focus.foreground_pixels,
            "foreground_ratio": round(focus.foreground_ratio, 4),
        },
    )
    return focus


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
    category = _normalize_token(clip.get("category"))
    if not category:
        return None, None

    scores = clip.get("scores", {})
    sub_scores = dict(scores.get("subcategory", {}))
    if sub_scores:
        selected, confidence = max(sub_scores.items(), key=lambda item: item[1])
        if confidence >= settings.ai_subcategory_confidence_threshold:
            return selected, float(confidence)

    candidate = _normalize_token(clip.get("subcategory"))
    candidate_conf = clip.get("subcategory_confidence") or 0.0
    if candidate:
        if candidate_conf >= settings.ai_subcategory_confidence_threshold:
            return candidate, float(candidate_conf)

    hint = _find_keyword_hint(category=category, image_path=image_path, colors=colors)
    if hint and hint.subcategory:
        return hint.subcategory, max(
            settings.ai_subcategory_confidence_threshold,
            _SUBCATEGORY_FALLBACK_CONFIDENCE,
        )
    return candidate or None, float(candidate_conf) if candidate else None


def _apply_subcategory_selection(
    clip: ClipPrediction,
    *,
    image_path: Path,
    colors: color.ColorResult,
) -> None:
    subcategory, confidence = _select_subcategory(
        clip=clip,
        image_path=image_path,
        colors=colors,
    )
    clip["subcategory"] = subcategory
    clip["subcategory_confidence"] = confidence
    scores = clip.setdefault("scores", {})
    sub_scores = dict(scores.get("subcategory", {}))
    if subcategory and confidence is not None:
        sub_scores[subcategory] = confidence
    scores["subcategory"] = sub_scores


def _score_list(labels: tuple[str, ...], *, base: float) -> list[tuple[str, float]]:
    seen: set[str] = set()
    results: list[tuple[str, float]] = []
    valid = {*MATERIAL_LABELS, *STYLE_LABELS, *ATTRIBUTE_LABELS}
    for label in labels:
        normalized = _normalize_token(label)
        if not normalized or normalized in seen or normalized not in valid:
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
    attribute_labels: list[tuple[str, float]] = []
    if hint:
        material_labels.extend(_score_list(hint.materials, base=0.7))
        style_labels.extend(_score_list(hint.style_tags, base=0.68))
        attribute_labels.extend(_score_list(hint.attribute_tags, base=0.64))

    material_scores = dict(material_labels)
    style_scores = dict(style_labels)
    attribute_scores = dict(attribute_labels)
    sub_scores: dict[str, float] = {}
    if subcategory and subcategory_conf is not None:
        sub_scores[subcategory] = subcategory_conf

    return cast(
        "ClipPrediction",
        {
            "category": category,
            "category_confidence": category_conf,
            "materials": material_labels,
            "style_tags": style_labels,
            "attribute_tags": attribute_labels,
            "subcategory": subcategory,
            "subcategory_confidence": subcategory_conf,
            "scores": {
                "category": {category: category_conf},
                "materials": material_scores,
                "style_tags": style_scores,
                "attribute_tags": attribute_scores,
                "subcategory": sub_scores,
            },
            "model_name": "heuristic",
        },
    )


def run(image_path: Path) -> PipelineResult:
    preprocessing_started = time.perf_counter()
    source_image = _load_source_image(image_path)
    focus = _prepare_focus_image(source_image)
    preprocessing_duration_ms = round((time.perf_counter() - preprocessing_started) * 1000, 2)

    color_started = time.perf_counter()
    color_result = _get_color_result(focus)
    color_duration_ms = round((time.perf_counter() - color_started) * 1000, 2)
    LOGGER.info(
        "ai.pipeline.color_prediction",
        extra={
            "primary_color": color_result.primary_color,
            "primary_color_confidence": color_result.confidence,
            "secondary_color": color_result.secondary_color,
            "secondary_color_confidence": color_result.secondary_confidence,
        },
    )

    cached = False
    embedding: np.ndarray | None = None
    embedding_model: str | None = None
    embedding_duration_ms = 0.0
    prediction_duration_ms = 0.0

    if not settings.ai_enable_classifier:
        clip_result = _heuristic_prediction(image_path, color_result)
        LOGGER.info(
            "ai.pipeline.heuristic_prediction",
            extra={
                "category": clip_result.get("category"),
                "category_confidence": clip_result.get("category_confidence"),
                "subcategory": clip_result.get("subcategory"),
                "subcategory_confidence": clip_result.get("subcategory_confidence"),
                "materials": clip_result.get("materials", [])[:3],
                "style_tags": clip_result.get("style_tags", [])[:3],
                "attribute_tags": clip_result.get("attribute_tags", [])[:3],
            },
        )
    else:
        try:
            predictor = _get_predictor()
            classifier_image = focus.masked_image if focus.mask is not None else focus.image
            embedding_started = time.perf_counter()
            embedding, cached = _load_embedding(
                image_path,
                predictor,
                image=classifier_image,
            )
            embedding_duration_ms = round((time.perf_counter() - embedding_started) * 1000, 2)
            embedding_model = getattr(predictor, "model_name", None)
            prediction_started = time.perf_counter()
            clip_result = predictor.predict(embedding)
            prediction_duration_ms = round((time.perf_counter() - prediction_started) * 1000, 2)
            _apply_subcategory_selection(
                clip_result,
                image_path=image_path,
                colors=color_result,
            )
            LOGGER.info(
                "ai.pipeline.clip_prediction",
                extra={
                    "category": clip_result.get("category"),
                    "category_confidence": clip_result.get("category_confidence"),
                    "subcategory": clip_result.get("subcategory"),
                    "subcategory_confidence": clip_result.get("subcategory_confidence"),
                    "materials": clip_result.get("materials", [])[:3],
                    "style_tags": clip_result.get("style_tags", [])[:3],
                    "attribute_tags": clip_result.get("attribute_tags", [])[:3],
                    "model_name": clip_result.get("model_name"),
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

    inference_duration_ms = round(
        color_duration_ms + embedding_duration_ms + prediction_duration_ms,
        2,
    )
    LOGGER.info(
        "ai.pipeline.timings",
        extra={
            "image_path": str(image_path),
            "cached": cached,
            "preprocessing_duration_ms": preprocessing_duration_ms,
            "color_duration_ms": color_duration_ms,
            "embedding_duration_ms": embedding_duration_ms,
            "prediction_duration_ms": prediction_duration_ms,
            "inference_duration_ms": inference_duration_ms,
            "foreground_ratio": round(focus.foreground_ratio, 4),
            "preprocessing_method": focus.method or "none",
        },
    )
    return PipelineResult(
        colors=color_result,
        clip=clip_result,
        cached=cached,
        embedding=embedding,
        embedding_model=embedding_model,
        preprocessing_duration_ms=preprocessing_duration_ms,
        color_duration_ms=color_duration_ms,
        embedding_duration_ms=embedding_duration_ms,
        prediction_duration_ms=prediction_duration_ms,
        inference_duration_ms=inference_duration_ms,
        foreground_ratio=focus.foreground_ratio,
        preprocessing_method=focus.method,
    )
