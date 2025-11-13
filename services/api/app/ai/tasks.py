"""Background tasks for AI-assisted wardrobe enrichment."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai import pipeline
from app.ai.pipeline import PipelineResult
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.wardrobe import WardrobeItem
from app.services import items as items_service
from app.utils import s3 as s3_utils

LOGGER = logging.getLogger("app.ai.tasks")


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
        if not item.image_url:
            LOGGER.debug("ai.tasks.skipped_no_image", extra={"item_id": str(item_id)})
            return

        image_path, cleanup_path = _prepare_image(item.image_url)
        if image_path is None:
            LOGGER.warning(
                "ai.tasks.image_unavailable",
                extra={"item_id": str(item_id), "image_url": item.image_url},
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

        _apply_classification(session, item, pipeline_result)


def _prepare_image(image_url: str) -> tuple[Path | None, bool]:
    """Return a local path to the image and whether it should be cleaned up."""
    parsed = urlparse(image_url)
    # Local mode: relative URLs served from MEDIA_ROOT.
    if not parsed.scheme or parsed.scheme == "" or parsed.scheme == "file":
        return _resolve_local_image(Path(parsed.path or image_url)), False
    if parsed.scheme in {"http", "https"}:
        if settings.is_s3_enabled and settings.aws_region and settings.s3_bucket_name:
            return _download_from_s3(parsed.path), True
        # If we are not in S3 mode, treat as local path within the same host.
        return _resolve_local_image(Path(parsed.path)), False
    return None, False


def _resolve_local_image(path: Path) -> Path | None:
    media_prefix = settings.media_url_path.rstrip("/")
    candidate = path.as_posix()
    if candidate.startswith("http"):
        candidate = urlparse(candidate).path
    if media_prefix and candidate.startswith(media_prefix):
        relative = candidate[len(media_prefix) :].lstrip("/")
    else:
        relative = candidate.lstrip("/")
    local_path = settings.media_root_path / relative
    if local_path.exists():
        return local_path
    return None


def _download_from_s3(object_path: str) -> Path | None:
    key = object_path.lstrip("/")
    if not key:
        return None
    try:
        data = s3_utils.download_object(
            bucket=settings.s3_bucket_name,  # type: ignore[arg-type]
            key=key,
            region=settings.aws_region,  # type: ignore[arg-type]
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("ai.tasks.s3_download_failed", extra={"key": key, "error": str(exc)})
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="styleus_ai_"))
    tmp_path = tmp_dir / Path(key).name
    tmp_path.write_bytes(data)
    return tmp_path


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

    existing_tags = [tag.tag for tag in item.tags]
    suggested_tags: list[str] = []
    for name, score in clip.get("materials", []):
        if score >= threshold:
            suggested_tags.append(name)
    for name, score in clip.get("styles", []):
        if score >= threshold:
            suggested_tags.append(name)

    if not existing_tags and suggested_tags:
        unique_tags = sorted({tag.strip() for tag in suggested_tags if tag.strip()})
        if unique_tags:
            update_kwargs["tags"] = unique_tags[:10]
    elif existing_tags and suggested_tags:
        combined = existing_tags + [
            tag for tag in suggested_tags if tag not in existing_tags
        ]
        combined = combined[:10]
        if combined != existing_tags:
            update_kwargs["tags"] = combined

    if update_kwargs:
        update_kwargs["ai_confidence"] = category_conf
        items_service.update_item(session, item, **update_kwargs)
        LOGGER.info(
            "ai.tasks.updated_item",
            extra={
                "item_id": str(item.id),
                "category": update_kwargs.get("category", item.category),
                "primary_color": update_kwargs.get("primary_color", item.primary_color),
                "secondary_color": update_kwargs.get("secondary_color", item.secondary_color),
                "tags": update_kwargs.get("tags", existing_tags),
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

    if not item.image_url:
        return None

    image_path, cleanup_required = _prepare_image(item.image_url)
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
