"""Background tasks for AI-assisted wardrobe enrichment."""

from __future__ import annotations

import logging
import tempfile
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


def classify_and_update_item(item_id: UUID) -> None:
    """Run classification for the given wardrobe item and persist predictions."""
    if not settings.ai_enable_classifier:
        LOGGER.debug("ai.tasks.skipped_disabled", extra={"item_id": str(item_id)})
        return

    with SessionLocal() as session:
        item = session.get(WardrobeItem, item_id)
        if item is None:
            LOGGER.debug("ai.tasks.missing_item", extra={"item_id": str(item_id)})
            return
        if item.deleted_at is not None:
            LOGGER.debug("ai.tasks.skipped_deleted", extra={"item_id": str(item_id)})
            return
        if not item.image_object_path and not item.image_url:
            LOGGER.debug("ai.tasks.skipped_no_image", extra={"item_id": str(item_id)})
            return

        image_path, cleanup_path = _prepare_item_image(item)
        if image_path is None:
            LOGGER.warning(
                "ai.tasks.image_unavailable",
                extra={
                    "item_id": str(item_id),
                    "image_object_path": item.image_object_path,
                    "image_url": item.image_url,
                },
            )
            return

        try:
            pipeline_result = pipeline.run(image_path)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception(
                "ai.tasks.classification_failed",
                extra={"item_id": str(item_id), "error": str(exc)},
            )
            if cleanup_path:
                _safe_unlink(image_path)
            return
        finally:
            if cleanup_path:
                _safe_unlink(image_path)

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
        _apply_classification(session, item, pipeline_result)


def _prepare_item_image(item: WardrobeItem) -> tuple[Path | None, bool]:
    if item.image_object_path:
        return _download_from_storage(item.image_object_path)
    if item.image_url:
        return _prepare_legacy_image(item.image_url)
    return None, False


def _prepare_legacy_image(image_url: str) -> tuple[Path | None, bool]:
    """Return a local path to the image and whether it should be cleaned up."""
    parsed = urlparse(image_url)
    if not parsed.scheme or parsed.scheme == "" or parsed.scheme == "file":
        return _resolve_local_image(Path(parsed.path or image_url)), False
    if parsed.scheme in {"http", "https"}:
        return _resolve_local_image(Path(parsed.path)), False
    return None, False


def _resolve_local_image(path: Path) -> Path | None:
    candidate = path.as_posix()
    if candidate.startswith("http"):
        candidate = urlparse(candidate).path
    local_path = settings.media_root_path / candidate.lstrip("/")
    if local_path.exists():
        return local_path
    return None


def _download_from_storage(object_path: str) -> tuple[Path | None, bool]:
    key = object_path.lstrip("/")
    if not key:
        return None, False
    try:
        downloaded = storage_utils.get_storage_adapter(settings).download_object(key)
    except storage_utils.SupabaseStorageError as exc:  # pragma: no cover - defensive
        LOGGER.warning("ai.tasks.storage_download_failed", extra={"key": key, "error": str(exc)})
        return None, False

    tmp_dir = Path(tempfile.mkdtemp(prefix="styleus_ai_"))
    tmp_path = tmp_dir / Path(key).name
    tmp_path.write_bytes(downloaded.data)
    return tmp_path, True


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
) -> None:
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
    else:
        if item.ai_confidence != category_conf:
            item.ai_confidence = category_conf
            session.add(item)
            session.commit()
        LOGGER.debug(
            "ai.tasks.no_update_needed",
            extra={"item_id": str(item.id)},
        )


def get_pipeline_preview(item: WardrobeItem) -> PipelineResult | None:
    """Run the AI pipeline for an item without persisting side effects."""

    if not item.image_object_path and not item.image_url:
        return None

    image_path, cleanup_required = _prepare_item_image(item)
    if image_path is None:
        return None

    try:
        return pipeline.run(image_path)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "ai.tasks.preview_failed",
            extra={"item_id": str(item.id), "error": str(exc)},
        )
        return None
    finally:
        if cleanup_required:
            _safe_unlink(image_path)
