"""Wardrobe item service logic."""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.models.user import User
from app.models.wardrobe import ItemTag, WardrobeItem
from app.schemas.items import ImageMetadata, ItemDetail
from app.services.search import apply_search_filters


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
) -> Sequence[WardrobeItem]:
    """Retrieve items for a user applying filters and pagination."""
    stmt: Select[tuple[WardrobeItem]] = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id)
        .options(selectinload(WardrobeItem.tags))
    )

    if not include_deleted:
        stmt = stmt.where(WardrobeItem.deleted_at.is_(None))

    if category:
        stmt = stmt.where(WardrobeItem.category == category)

    if query:
        stmt = apply_search_filters(stmt, query)
        stmt = stmt.distinct()

    stmt = stmt.order_by(WardrobeItem.created_at.desc()).limit(limit).offset(offset)

    result = db.execute(stmt)
    return result.scalars().all()


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
        .options(selectinload(WardrobeItem.tags))
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
    color: str | None = None,
    brand: str | None = None,
    tags: list[str] | None = None,
    subcategory: str | None = None,
    primary_color: str | None = None,
    secondary_color: str | None = None,
    ai_confidence: float | None = None,
) -> WardrobeItem:
    """Persist field updates and normalized tag values for an item."""
    if category is not None:
        item.category = category
    if color is not None:
        item.color = color
    if brand is not None:
        item.brand = brand
    if subcategory is not None:
        item.subcategory = subcategory
    if primary_color is not None:
        item.primary_color = primary_color
    if secondary_color is not None:
        item.secondary_color = secondary_color
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
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: WardrobeItem) -> None:
    """Soft delete an item by marking its deletion timestamp."""

    if item.deleted_at is None:
        item.deleted_at = datetime.datetime.now(tz=datetime.UTC)
        db.add(item)
        db.commit()


def complete_upload(
    db: Session,
    item: WardrobeItem,
    image_url: str | None,
    *,
    thumb_url: str | None = None,
    medium_url: str | None = None,
    metadata: ImageMetadata | None = None,
) -> WardrobeItem:
    """Store the image URL on an item once uploads finish."""
    item.image_url = image_url
    item.image_thumb_url = thumb_url
    item.image_medium_url = medium_url

    if metadata is not None:
        item.image_width = metadata.width
        item.image_height = metadata.height
        item.image_bytes = metadata.bytes
        item.image_mime_type = metadata.mime_type
        item.image_checksum = metadata.checksum

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def to_item_detail(item: WardrobeItem) -> ItemDetail:
    """Convert an ORM object into a Pydantic response model."""
    metadata: ImageMetadata | None = None
    if any(
        value is not None
        for value in (
            item.image_width,
            item.image_height,
            item.image_bytes,
            item.image_mime_type,
            item.image_checksum,
        )
    ):
        metadata = ImageMetadata(
            width=item.image_width,
            height=item.image_height,
            bytes=item.image_bytes,
            mime_type=item.image_mime_type,
            checksum=item.image_checksum,
        )

    return ItemDetail.model_validate(
        {
            "id": item.id,
            "category": item.category,
            "color": item.color,
            "brand": item.brand,
            "subcategory": item.subcategory,
            "primary_color": item.primary_color,
            "secondary_color": item.secondary_color,
            "image_url": item.image_url,
            "thumb_url": item.image_thumb_url,
            "medium_url": item.image_medium_url,
            "created_at": item.created_at,
            "tags": [tag.tag for tag in item.tags],
            "image_metadata": metadata.model_dump(by_alias=True) if metadata else None,
            "ai_confidence": item.ai_confidence,
        }
    )


def _ensure_user(db: Session, user_id: uuid.UUID) -> User:
    """Guarantee the backing user row exists before creating child objects."""
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=f"user-{user_id}@example.com")
        db.add(user)
        db.flush()
    return user
