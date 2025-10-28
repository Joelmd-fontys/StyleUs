"""Wardrobe item service logic."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.models.wardrobe import ItemTag, WardrobeItem
from app.schemas.items import ItemDetail
from app.services.search import apply_search_filters


def create_placeholder_item(db: Session, user_id: uuid.UUID) -> WardrobeItem:
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
) -> Sequence[WardrobeItem]:
    stmt: Select[tuple[WardrobeItem]] = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id)
        .options(selectinload(WardrobeItem.tags))
    )

    if category:
        stmt = stmt.where(WardrobeItem.category == category)

    if query:
        stmt = apply_search_filters(stmt, query)
        stmt = stmt.distinct()

    stmt = stmt.order_by(WardrobeItem.created_at.desc()).limit(limit).offset(offset)

    result = db.execute(stmt)
    return result.scalars().all()


def get_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> WardrobeItem | None:
    stmt = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id, WardrobeItem.id == item_id)
        .options(selectinload(WardrobeItem.tags))
    )
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
) -> WardrobeItem:
    if category is not None:
        item.category = category
    if color is not None:
        item.color = color
    if brand is not None:
        item.brand = brand

    if tags is not None:
        normalized = sorted({tag.strip() for tag in tags if tag.strip()})
        item.tags.clear()
        for tag in normalized:
            item.tags.append(ItemTag(tag=tag))

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def complete_upload(db: Session, item: WardrobeItem, image_url: str) -> WardrobeItem:
    item.image_url = image_url
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def to_item_detail(item: WardrobeItem) -> ItemDetail:
    return ItemDetail.model_validate(
        {
            "id": item.id,
            "category": item.category,
            "color": item.color,
            "brand": item.brand,
            "image_url": item.image_url,
            "created_at": item.created_at,
            "tags": [tag.tag for tag in item.tags],
        }
    )


def _ensure_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=f"user-{user_id}@example.com")
        db.add(user)
        db.flush()
    return user
