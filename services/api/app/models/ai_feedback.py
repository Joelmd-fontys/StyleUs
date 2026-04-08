"""AI review feedback event model."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

if TYPE_CHECKING:
    from app.models.wardrobe import WardrobeItem


class AIReviewFeedbackEvent(Base):
    __tablename__: str = "ai_review_feedback_events"  # type: ignore[assignment]

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("wardrobe_items.id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
    )
    predicted_category: Mapped[str | None] = mapped_column(
        String(length=100),
        nullable=True,
    )
    corrected_category: Mapped[str] = mapped_column(String(length=100), nullable=False)
    prediction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted_directly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(
        String(length=50),
        nullable=False,
        default="upload_review",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    item: Mapped[WardrobeItem] = relationship(
        "WardrobeItem",
        back_populates="review_feedback_events",
    )


Index(
    "ix_ai_review_feedback_events_item_created_at",
    AIReviewFeedbackEvent.item_id,
    AIReviewFeedbackEvent.created_at.desc(),
)
