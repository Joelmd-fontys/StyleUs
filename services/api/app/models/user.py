"""User model."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

if TYPE_CHECKING:
    from app.models.wardrobe import WardrobeItem


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["WardrobeItem"]] = relationship(
        "WardrobeItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
