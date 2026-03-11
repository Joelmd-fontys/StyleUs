"""Add durable AI job queue table."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "202603111100"
down_revision: str | None = "202603111000"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_jobs",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "item_id",
            GUID(),
            sa.ForeignKey("wardrobe_items.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_ai_jobs_status_created_at", "ai_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_status_created_at", table_name="ai_jobs")
    op.drop_table("ai_jobs")
