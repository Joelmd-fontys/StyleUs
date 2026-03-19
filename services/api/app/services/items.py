"""Wardrobe item service logic."""

from __future__ import annotations

import datetime
import logging
import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.core.config import Settings
from app.models.ai_job import AIJob, AIJobStatus
from app.models.user import User
from app.models.wardrobe import ItemTag, WardrobeItem
from app.schemas.items import AIJobState, ImageMetadata, ItemAIAttributes, ItemAIPreview, ItemDetail
from app.services.search import apply_search_filters
from app.utils import storage as storage_utils

_EMPTY_CATEGORY_VALUES = {"", "uncategorized"}
LOGGER = logging.getLogger("app.services.items")


def create_placeholder_item(db: Session, user_id: uuid.UUID) -> WardrobeItem:
    """Create a placeholder item attached to the user to reserve an identifier."""
    _ensure_user(db, user_id)
    item = WardrobeItem(
        user_id=user_id,
        category="uncategorized",
        color="unspecified",
        brand=None,
        image_url=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_items(
    db: Session,
    user_id: uuid.UUID,
    *,
    category: str | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_deleted: bool = False,
    created_since: datetime.datetime | None = None,
) -> Sequence[WardrobeItem]:
    """Retrieve items for a user applying filters and pagination."""
    stmt: Select[tuple[WardrobeItem]] = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id)
        .options(selectinload(WardrobeItem.tags), selectinload(WardrobeItem.ai_job))
    )

    if not include_deleted:
        stmt = stmt.where(WardrobeItem.deleted_at.is_(None))

    if category:
        stmt = stmt.where(WardrobeItem.category == category)

    if query:
        stmt = apply_search_filters(stmt, query)

    if created_since:
        stmt = stmt.where(WardrobeItem.created_at > created_since)

    stmt = stmt.order_by(WardrobeItem.created_at.desc()).limit(limit).offset(offset)

    result = db.execute(stmt)
    return result.scalars().unique().all()


def get_item(
    db: Session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> WardrobeItem | None:
    """Return a single wardrobe item for a user if it exists."""
    stmt = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id, WardrobeItem.id == item_id)
        .options(selectinload(WardrobeItem.tags), selectinload(WardrobeItem.ai_job))
    )
    if not include_deleted:
        stmt = stmt.where(WardrobeItem.deleted_at.is_(None))
    result = db.execute(stmt)
    return result.scalars().first()


def update_item(
    db: Session,
    item: WardrobeItem,
    *,
    category: str | None = None,
    subcategory: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    tags: list[str] | None = None,
    primary_color: str | None = None,
    secondary_color: str | None = None,
    ai_materials: list[str] | None = None,
    ai_style_tags: list[str] | None = None,
    ai_attribute_tags: list[str] | None = None,
    ai_embedding: list[float] | None = None,
    ai_embedding_model: str | None = None,
    ai_confidence: float | None = None,
    commit: bool = True,
) -> WardrobeItem:
    """Persist field updates and normalized tag values for an item."""
    if category is not None:
        item.category = category
    if subcategory is not None:
        item.subcategory = subcategory
    if color is not None:
        item.color = color
    if brand is not None:
        item.brand = brand
    if primary_color is not None:
        item.primary_color = primary_color
    if secondary_color is not None:
        item.secondary_color = secondary_color
    if ai_materials is not None:
        item.ai_materials = ai_materials
    if ai_style_tags is not None:
        item.ai_style_tags = ai_style_tags
    if ai_attribute_tags is not None:
        item.ai_attribute_tags = ai_attribute_tags
    if ai_embedding is not None:
        item.ai_embedding = ai_embedding
    if ai_embedding_model is not None:
        item.ai_embedding_model = ai_embedding_model
    if ai_confidence is not None:
        item.ai_confidence = ai_confidence

    if tags is not None:
        normalized = sorted(
            {tag.strip() for tag in tags if tag.strip()},
        )
        item.tags.clear()
        for tag in normalized:
            item.tags.append(ItemTag(tag=tag))

    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def delete_item(db: Session, item: WardrobeItem) -> None:
    """Soft delete an item by marking its deletion timestamp."""

    if item.deleted_at is None:
        now = datetime.datetime.now(tz=datetime.UTC)
        item.deleted_at = now
        if item.ai_job and item.ai_job.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
        }:
            item.ai_job.status = AIJobStatus.FAILED.value
            item.ai_job.completed_at = now
            item.ai_job.error_message = "Wardrobe item deleted before AI enrichment"
            db.add(item.ai_job)
        db.add(item)
        db.commit()


def complete_upload(
    db: Session,
    item: WardrobeItem,
    image_object_path: str | None,
    *,
    thumb_object_path: str | None = None,
    medium_object_path: str | None = None,
    metadata: ImageMetadata | None = None,
    commit: bool = True,
) -> WardrobeItem:
    """Store image object paths on an item once uploads finish."""
    item.image_object_path = image_object_path
    item.image_thumb_object_path = thumb_object_path
    item.image_medium_object_path = medium_object_path
    item.image_url = None
    item.image_thumb_url = None
    item.image_medium_url = None

    if metadata is not None:
        item.image_width = metadata.width
        item.image_height = metadata.height
        item.image_bytes = metadata.bytes
        item.image_mime_type = metadata.mime_type
        item.image_checksum = metadata.checksum

    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def build_signed_media_urls(
    settings: Settings,
    items: Sequence[WardrobeItem],
) -> dict[str, str]:
    """Resolve temporary signed URLs for all private media paths referenced by the items."""
    object_paths = collect_media_object_paths(items)
    if not object_paths:
        return {}
    try:
        return storage_utils.get_storage_adapter(settings).create_signed_urls(object_paths)
    except storage_utils.SupabaseStorageError as exc:
        LOGGER.warning("items.sign_media_failed", extra={"error": str(exc)})
        return {}


def collect_media_object_paths(items: Sequence[WardrobeItem]) -> list[str]:
    """Collect distinct media object paths referenced by the provided items."""
    paths: list[str] = []
    for item in items:
        for path in (
            item.image_object_path,
            item.image_medium_object_path,
            item.image_thumb_object_path,
        ):
            if path:
                paths.append(path)
    return list(dict.fromkeys(paths))


def to_item_detail(
    item: WardrobeItem,
    *,
    signed_urls: Mapping[str, str] | None = None,
) -> ItemDetail:
    """Convert an ORM object into a Pydantic response model."""
    metadata = _build_image_metadata(item)
    ai_block = _build_item_ai_attributes(item)
    image_url, medium_url, thumb_url = _resolve_image_urls(item, signed_urls=signed_urls)

    return ItemDetail.model_validate(
        {
            "id": item.id,
            "category": item.category,
            "subcategory": item.subcategory,
            "color": item.color,
            "brand": item.brand,
            "primary_color": item.primary_color,
            "secondary_color": item.secondary_color,
            "image_url": image_url,
            "thumb_url": thumb_url,
            "medium_url": medium_url,
            "created_at": item.created_at,
            "tags": [tag.tag for tag in item.tags],
            "image_metadata": metadata.model_dump(by_alias=True) if metadata else None,
            "ai_confidence": item.ai_confidence,
            "ai": ai_block.model_dump(by_alias=True) if ai_block else None,
            "ai_job": _build_ai_job_state(item.ai_job),
        }
    )


def _resolve_image_urls(
    item: WardrobeItem,
    *,
    signed_urls: Mapping[str, str] | None = None,
) -> tuple[str | None, str | None, str | None]:
    signed_urls = signed_urls or {}
    image_url = signed_urls.get(item.image_object_path or "") if item.image_object_path else None
    medium_url = (
        signed_urls.get(item.image_medium_object_path or "")
        if item.image_medium_object_path
        else None
    )
    thumb_url = (
        signed_urls.get(item.image_thumb_object_path or "")
        if item.image_thumb_object_path
        else None
    )
    return (
        image_url or item.image_url,
        medium_url or item.image_medium_url,
        thumb_url or item.image_thumb_url,
    )


def to_ai_preview(item: WardrobeItem) -> ItemAIPreview:
    """Build an AI preview payload from persisted item and job state."""
    return _build_base_ai_preview(item)


def _ensure_user(db: Session, user_id: uuid.UUID) -> User:
    """Guarantee the backing user row exists before creating child objects."""
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=f"user-{user_id}@styleus.invalid")
        db.add(user)
        db.flush()
    return user


def _normalized_item_category(item: WardrobeItem) -> str | None:
    if item.category in _EMPTY_CATEGORY_VALUES:
        return None
    return item.category


def _build_image_metadata(item: WardrobeItem) -> ImageMetadata | None:
    if not any(
        value is not None
        for value in (
            item.image_width,
            item.image_height,
            item.image_bytes,
            item.image_mime_type,
            item.image_checksum,
        )
    ):
        return None

    return ImageMetadata.model_validate(
        {
            "width": item.image_width,
            "height": item.image_height,
            "bytes": item.image_bytes,
            "mime_type": item.image_mime_type,
            "checksum": item.image_checksum,
        }
    )


def _build_item_ai_attributes(item: WardrobeItem) -> ItemAIAttributes | None:
    if not any(
        value
        for value in (
            item.ai_confidence,
            item.ai_materials,
            item.ai_style_tags,
            item.ai_attribute_tags,
            item.subcategory,
        )
    ):
        return None

    return ItemAIAttributes.model_validate(
        {
            "category": _normalized_item_category(item),
            "subcategory": item.subcategory,
            "materials": item.ai_materials or [],
            "style_tags": (item.ai_style_tags or [])[:3],
            "attributes": (item.ai_attribute_tags or [])[:3],
            "confidence": item.ai_confidence,
        }
    )


def _build_base_ai_preview(item: WardrobeItem) -> ItemAIPreview:
    job_state = _build_ai_job_state(item.ai_job)
    payload = _build_job_preview_payload(item.ai_job)
    return ItemAIPreview.model_validate(
        {
            "category": payload.get("category", _normalized_item_category(item)),
            "category_confidence": payload.get("category_confidence", item.ai_confidence),
            "subcategory": payload.get("subcategory", item.subcategory),
            "subcategory_confidence": payload.get("subcategory_confidence"),
            "primary_color": payload.get("primary_color", item.primary_color or None),
            "primary_color_confidence": payload.get("primary_color_confidence"),
            "secondary_color": payload.get("secondary_color", item.secondary_color or None),
            "secondary_color_confidence": payload.get("secondary_color_confidence"),
            "materials": payload.get("materials", list(item.ai_materials or [])),
            "style_tags": payload.get("style_tags", list(item.ai_style_tags or [])[:3]),
            "attributes": payload.get("attributes", list(item.ai_attribute_tags or [])[:3]),
            "tags": payload.get("tags", [tag.tag for tag in item.tags]),
            "tag_confidences": payload.get("tag_confidences", {}),
            "confidence": payload.get("confidence", item.ai_confidence),
            "uncertain": payload.get("uncertain", False),
            "uncertain_fields": payload.get("uncertain_fields", []),
            "pending": bool(job_state and job_state.pending),
            "job": job_state.model_dump(by_alias=True) if job_state else None,
        }
    )


def _build_ai_job_state(job: AIJob | None) -> AIJobState | None:
    if job is None:
        return None

    pending = job.status in {AIJobStatus.PENDING.value, AIJobStatus.RUNNING.value}
    return AIJobState.model_validate(
        {
            "id": job.id,
            "status": job.status,
            "attempts": job.attempts,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "pending": pending,
        }
    )


def _build_job_preview_payload(job: AIJob | None) -> dict[str, object]:
    if job is None or not isinstance(job.result_payload, dict):
        return {}
    return dict(job.result_payload)
