"""Shared AI enrichment helpers used by the worker."""

from __future__ import annotations

import time
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai import pipeline
from app.ai.pipeline import PipelineResult
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.wardrobe import WardrobeItem
from app.services import items as items_service
from app.utils import storage as storage_utils

LOGGER = logging.getLogger("app.ai.tasks")


class AIEnrichmentError(RuntimeError):
    """Base error raised while preparing or running item enrichment."""

    retryable = True


class RetryableAIEnrichmentError(AIEnrichmentError):
    retryable = True


class NonRetryableAIEnrichmentError(AIEnrichmentError):
    retryable = False


@dataclass(frozen=True, slots=True)
class PreparedItemImage:
    path: Path
    cleanup_required: bool
    source: str
    fetch_duration_ms: float
    bytes_size: int | None = None


def select_top_tags(
    clip: pipeline.ClipPrediction, *, threshold: float, limit: int = 3
) -> list[tuple[str, float]]:
    """Return up to ``limit`` highest-confidence tag names across materials + styles."""

    scores: dict[str, float] = {}
    for name, score in clip.get("materials", []):
        if score >= threshold:
            scores[name] = max(scores.get(name, 0.0), float(score))
    for name, score in clip.get("style_tags", []):
        if score >= threshold:
            scores[name] = max(scores.get(name, 0.0), float(score))

    ordered = sorted(scores.items(), key=lambda entry: entry[1], reverse=True)
    return ordered[:limit]


def build_ai_preview_payload(result: PipelineResult) -> dict[str, object]:
    """Serialize the full AI suggestion set for durable preview responses."""

    clip = result.clip
    color_result = result.colors
    materials = [name for name, _score in clip.get("materials", [])[:5]]
    style_tags = [name for name, _score in clip.get("style_tags", [])[:5]]
    tags = [name for name, _score in select_top_tags(clip, threshold=0.0, limit=3)]

    payload = {
        "category": clip.get("category"),
        "category_confidence": clip.get("category_confidence"),
        "subcategory": clip.get("subcategory"),
        "subcategory_confidence": clip.get("subcategory_confidence"),
        "primary_color": _normalize_preview_color(color_result.primary_color),
        "primary_color_confidence": color_result.confidence,
        "secondary_color": _normalize_preview_color(color_result.secondary_color),
        "secondary_color_confidence": color_result.secondary_confidence,
        "materials": materials,
        "style_tags": style_tags,
        "tags": tags,
        "confidence": clip.get("category_confidence"),
    }
    LOGGER.info(
        "ai.tasks.preview_payload_built",
        extra={
            "category": payload["category"],
            "subcategory": payload["subcategory"],
            "primary_color": payload["primary_color"],
            "secondary_color": payload["secondary_color"],
            "tags": payload["tags"],
        },
    )
    return payload


def classify_and_update_item(item_id: UUID) -> None:
    """Run classification for the given wardrobe item and persist predictions."""
    if not settings.ai_enable_classifier:
        LOGGER.debug("ai.tasks.skipped_disabled", extra={"item_id": str(item_id)})
        return

    with SessionLocal() as session:
        try:
            run_item_enrichment(session, item_id)
        except NonRetryableAIEnrichmentError as exc:
            LOGGER.warning(
                "ai.tasks.non_retryable_failure",
                extra={"item_id": str(item_id), "error": str(exc)},
            )
        except RetryableAIEnrichmentError as exc:
            LOGGER.warning(
                "ai.tasks.retryable_failure",
                extra={"item_id": str(item_id), "error": str(exc)},
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception(
                "ai.tasks.unexpected_failure",
                extra={"item_id": str(item_id), "error": str(exc)},
            )


def run_item_enrichment(
    session: Session,
    item_id: UUID,
    *,
    commit: bool = True,
) -> PipelineResult:
    """Run the shared AI pipeline for an item inside the provided session."""

    total_started = time.perf_counter()
    item = session.get(WardrobeItem, item_id)
    if item is None:
        raise NonRetryableAIEnrichmentError("Wardrobe item not found")
    if item.deleted_at is not None:
        raise NonRetryableAIEnrichmentError("Wardrobe item is deleted")
    if not item.image_object_path and not item.image_url:
        raise NonRetryableAIEnrichmentError("Wardrobe item has no image")

    LOGGER.info(
        "ai.tasks.image_fetch_started",
        extra={
            "item_id": str(item.id),
            "preferred_source": (
                "storage_medium"
                if item.image_medium_object_path
                else "storage_original"
                if item.image_object_path
                else "legacy"
            ),
        },
    )
    prepared_image = _prepare_item_image(item)
    if prepared_image is None:
        raise RetryableAIEnrichmentError("Wardrobe item image is unavailable")
    LOGGER.info(
        "ai.tasks.image_fetched",
        extra={
            "item_id": str(item.id),
            "source": prepared_image.source,
            "image_path": str(prepared_image.path),
            "fetch_duration_ms": prepared_image.fetch_duration_ms,
            "bytes_size": prepared_image.bytes_size,
        },
    )

    LOGGER.info(
        "ai.tasks.inference_started",
        extra={"item_id": str(item.id), "image_path": str(prepared_image.path)},
    )
    try:
        pipeline_result = pipeline.run(prepared_image.path)
    except Exception as exc:  # pragma: no cover - defensive
        raise RetryableAIEnrichmentError(f"AI pipeline failed: {exc}") from exc
    finally:
        if prepared_image.cleanup_required:
            _safe_unlink(prepared_image.path)

    LOGGER.debug(
        "ai.tasks.prediction",
        extra={
            "item_id": str(item.id),
            "category": pipeline_result.clip.get("category"),
            "subcategory": pipeline_result.clip.get("subcategory"),
            "category_confidence": pipeline_result.clip.get("category_confidence"),
            "subcategory_confidence": pipeline_result.clip.get("subcategory_confidence"),
        },
    )
    db_write_started = time.perf_counter()
    LOGGER.info("ai.tasks.db_update_started", extra={"item_id": str(item.id)})
    updated_fields = _apply_classification(session, item, pipeline_result, commit=commit)
    db_write_duration_ms = round((time.perf_counter() - db_write_started) * 1000, 2)
    LOGGER.info(
        "ai.tasks.db_updated",
        extra={
            "item_id": str(item.id),
            "updated_fields": updated_fields,
            "db_write_duration_ms": db_write_duration_ms,
            "total_duration_ms": round((time.perf_counter() - total_started) * 1000, 2),
        },
    )
    return pipeline_result


def _prepare_item_image(item: WardrobeItem) -> PreparedItemImage | None:
    storage_candidates: list[tuple[str, str]] = []
    if item.image_medium_object_path:
        storage_candidates.append((item.image_medium_object_path, "storage_medium"))
    if item.image_object_path and item.image_object_path != item.image_medium_object_path:
        storage_candidates.append((item.image_object_path, "storage_original"))
    for object_path, source in storage_candidates:
        prepared = _download_from_storage(
            object_path,
            source=source,
            cache_key=item.image_checksum,
        )
        if prepared is not None:
            return prepared
        LOGGER.warning(
            "ai.tasks.image_fetch_fallback",
            extra={
                "item_id": str(item.id),
                "object_path": object_path,
                "source": source,
            },
        )
    if item.image_url:
        return _prepare_legacy_image(item.image_url)
    return None


def _normalize_preview_color(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in {"unknown", "unspecified"}:
        return None
    return normalized


def _prepare_legacy_image(image_url: str) -> PreparedItemImage | None:
    """Return a local path to the image and whether it should be cleaned up."""
    parsed = urlparse(image_url)
    if not parsed.scheme or parsed.scheme == "" or parsed.scheme == "file":
        path = _resolve_local_image(Path(parsed.path or image_url))
        if path is None:
            return None
        return PreparedItemImage(
            path=path,
            cleanup_required=False,
            source="legacy_local",
            fetch_duration_ms=0.0,
        )
    if parsed.scheme in {"http", "https"}:
        path = _resolve_local_image(Path(parsed.path))
        if path is None:
            return None
        return PreparedItemImage(
            path=path,
            cleanup_required=False,
            source="legacy_http_local",
            fetch_duration_ms=0.0,
        )
    return None


def _resolve_local_image(path: Path) -> Path | None:
    candidate = path.as_posix()
    if candidate.startswith("http"):
        candidate = urlparse(candidate).path
    local_path = settings.media_root_path / candidate.lstrip("/")
    if local_path.exists():
        return local_path
    return None


def _download_from_storage(
    object_path: str,
    *,
    source: str,
    cache_key: str | None = None,
) -> PreparedItemImage | None:
    key = object_path.lstrip("/")
    if not key:
        return None
    fetch_started = time.perf_counter()
    try:
        downloaded = storage_utils.get_storage_adapter(settings).download_object(key)
    except storage_utils.SupabaseStorageError as exc:  # pragma: no cover - defensive
        LOGGER.warning("ai.tasks.storage_download_failed", extra={"key": key, "error": str(exc)})
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="styleus_ai_"))
    cache_prefix = (cache_key or "").strip().lower()
    file_name = Path(key).name
    if cache_prefix:
        tmp_path = tmp_dir / f"{cache_prefix}_{file_name}"
    else:
        tmp_path = tmp_dir / file_name
    tmp_path.write_bytes(downloaded.data)
    return PreparedItemImage(
        path=tmp_path,
        cleanup_required=True,
        source=source,
        fetch_duration_ms=round((time.perf_counter() - fetch_started) * 1000, 2),
        bytes_size=downloaded.size if downloaded.size else len(downloaded.data),
    )


def _safe_unlink(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
        if path.parent.name.startswith("styleus_ai_") and not any(path.parent.iterdir()):
            path.parent.rmdir()
    except Exception:  # pragma: no cover - best-effort cleanup
        LOGGER.debug("ai.tasks.cleanup_failed", extra={"path": str(path)})


def _apply_classification(
    session: Session,
    item: WardrobeItem,
    result: PipelineResult,
    *,
    commit: bool = True,
) -> list[str]:
    update_kwargs: dict[str, object] = {}
    threshold = settings.ai_confidence_threshold
    subcategory_threshold = settings.ai_subcategory_confidence_threshold

    color_result = result.colors
    if color_result.primary_color:
        if color_result.confidence >= threshold:
            if not item.primary_color:
                update_kwargs["primary_color"] = color_result.primary_color
            else:
                LOGGER.debug(
                    "ai.tasks.color_existing_primary",
                    extra={
                        "item_id": str(item.id),
                        "primary_color": item.primary_color,
                    },
                )
            if (
                not item.color
                or item.color.lower() in {"unspecified", "unknown", ""}
            ):
                update_kwargs["color"] = color_result.primary_color
            if (
                color_result.secondary_color
                and color_result.secondary_confidence
                and color_result.secondary_confidence >= threshold
                and not item.secondary_color
            ):
                update_kwargs["secondary_color"] = color_result.secondary_color
        else:
            LOGGER.debug(
                "ai.tasks.color_below_threshold",
                extra={
                    "item_id": str(item.id),
                    "predicted_color": color_result.primary_color,
                    "confidence": color_result.confidence,
                    "threshold": threshold,
                },
            )

    clip = result.clip
    category_conf = clip.get("category_confidence", 0.0)
    if (
        category_conf >= threshold
        and (not item.category or item.category in {"unknown", "uncategorized"})
    ):
        update_kwargs["category"] = clip["category"]

    subcategory_label = clip.get("subcategory")
    subcategory_conf = clip.get("subcategory_confidence") or 0.0
    if (
        subcategory_label
        and subcategory_conf >= subcategory_threshold
        and (not getattr(item, "subcategory", None) or item.subcategory in {"", "unspecified"})
    ):
        update_kwargs["subcategory"] = subcategory_label

    materials_above_threshold = [
        name for name, score in clip.get("materials", []) if score >= threshold
    ]
    style_tags_above_threshold = [
        name
        for name, score in sorted(
            clip.get("style_tags", []), key=lambda entry: entry[1], reverse=True
        )
        if score >= threshold
    ]
    if materials_above_threshold:
        update_kwargs["ai_materials"] = materials_above_threshold[:5]
    if style_tags_above_threshold:
        update_kwargs["ai_style_tags"] = style_tags_above_threshold[:3]

    existing_tags = [tag.tag for tag in item.tags]
    top_scored_tags = select_top_tags(clip, threshold=threshold, limit=3)
    suggested_tags = [name for name, _ in top_scored_tags]

    if not existing_tags and suggested_tags:
        update_kwargs["tags"] = suggested_tags
    elif existing_tags and suggested_tags:
        combined = existing_tags + [
            tag for tag in suggested_tags if tag not in existing_tags
        ]
        combined = combined[:10]
        if combined != existing_tags:
            update_kwargs["tags"] = combined

    if update_kwargs:
        items_service.update_item(
            session,
            item,
            category=cast(str | None, update_kwargs.get("category")),
            subcategory=cast(str | None, update_kwargs.get("subcategory")),
            color=cast(str | None, update_kwargs.get("color")),
            brand=cast(str | None, update_kwargs.get("brand")),
            tags=cast(list[str] | None, update_kwargs.get("tags")),
            primary_color=cast(str | None, update_kwargs.get("primary_color")),
            secondary_color=cast(str | None, update_kwargs.get("secondary_color")),
            ai_materials=cast(list[str] | None, update_kwargs.get("ai_materials")),
            ai_style_tags=cast(list[str] | None, update_kwargs.get("ai_style_tags")),
            ai_confidence=category_conf,
            commit=commit,
        )
        LOGGER.info(
            "ai.tasks.updated_item",
            extra={
                "item_id": str(item.id),
                "category": update_kwargs.get("category", item.category),
                "subcategory": update_kwargs.get("subcategory", getattr(item, "subcategory", None)),
                "primary_color": update_kwargs.get("primary_color", item.primary_color),
                "secondary_color": update_kwargs.get("secondary_color", item.secondary_color),
                "tags": update_kwargs.get("tags", existing_tags),
                "ai_materials": update_kwargs.get(
                    "ai_materials",
                    getattr(item, "ai_materials", None),
                ),
                "ai_style_tags": update_kwargs.get(
                    "ai_style_tags",
                    getattr(item, "ai_style_tags", None),
                ),
                "confidence": category_conf,
            },
        )
        return sorted(update_kwargs.keys())
    else:
        if item.ai_confidence != category_conf:
            item.ai_confidence = category_conf
            session.add(item)
            if commit:
                session.commit()
            else:
                session.flush()
            return ["ai_confidence"]
        LOGGER.debug(
            "ai.tasks.no_update_needed",
            extra={"item_id": str(item.id)},
        )
    return []


def get_pipeline_preview(item: WardrobeItem) -> PipelineResult | None:
    """Run the AI pipeline for an item without persisting side effects."""

    if not item.image_object_path and not item.image_url:
        return None

    prepared_image = _prepare_item_image(item)
    if prepared_image is None:
        return None

    try:
        return pipeline.run(prepared_image.path)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "ai.tasks.preview_failed",
            extra={"item_id": str(item.id), "error": str(exc)},
        )
        return None
    finally:
        if prepared_image.cleanup_required:
            _safe_unlink(prepared_image.path)
