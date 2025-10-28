"""Search helper utilities."""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.sql import Select

from app.models.wardrobe import ItemTag, WardrobeItem


def apply_search_filters(stmt: Select[tuple[WardrobeItem]], query: str) -> Select[tuple[WardrobeItem]]:
    """Apply case-insensitive search filters across brand and tags."""

    normalized = f"%{query.lower()}%"

    return stmt.outerjoin(ItemTag).where(
        or_(
            func.lower(func.coalesce(WardrobeItem.brand, "")).like(normalized),
            func.lower(ItemTag.tag).like(normalized),
        )
    )
