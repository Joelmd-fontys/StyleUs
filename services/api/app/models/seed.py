"""Database model tracking applied seed runs."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SeedRun(Base):
    __tablename__ = "seeds"

    key: Mapped[str] = mapped_column(String(length=100), primary_key=True)
    applied_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
