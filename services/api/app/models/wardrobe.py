"""Wardrobe item models."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

if TYPE_CHECKING:
    from app.models.user import User


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
    )
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_thumb_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_medium_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_width: Mapped[int | None] = mapped_column(nullable=True)
    image_height: Mapped[int | None] = mapped_column(nullable=True)
    image_bytes: Mapped[int | None] = mapped_column(nullable=True)
    image_mime_type: Mapped[str | None] = mapped_column(
        String(length=100),
        nullable=True,
    )
    image_checksum: Mapped[str | None] = mapped_column(
        String(length=128),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(length=100), nullable=False)
    color: Mapped[str] = mapped_column(String(length=100), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(length=100), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(length=50), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(length=50), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ai_confidence: Mapped[float | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship("User", back_populates="items")
    tags: Mapped[list[ItemTag]] = relationship(
        "ItemTag",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ItemTag(Base):
    __tablename__ = "item_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("wardrobe_items.id"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(String(length=100), nullable=False)

    item: Mapped[WardrobeItem] = relationship("WardrobeItem", back_populates="tags")


Index(
    "ix_wardrobe_items_user_created_at",
    WardrobeItem.user_id,
    WardrobeItem.created_at.desc(),
)
Index("ix_wardrobe_items_category", WardrobeItem.category)
Index("ix_item_tags_tag", ItemTag.tag)
