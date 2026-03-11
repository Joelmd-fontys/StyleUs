"""AI enrichment job queue models."""

from __future__ import annotations

import datetime
import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

if TYPE_CHECKING:
    from app.models.wardrobe import WardrobeItem


class AIJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AIJob(Base):
    __tablename__: str = "ai_jobs"  # type: ignore[assignment]

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("wardrobe_items.id"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(length=20),
        default=AIJobStatus.PENDING.value,
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[WardrobeItem] = relationship("WardrobeItem", back_populates="ai_job")


Index("ix_ai_jobs_status_created_at", AIJob.status, AIJob.created_at)
