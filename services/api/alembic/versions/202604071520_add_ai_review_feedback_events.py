"""Add AI review feedback events table."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "202604071520"
down_revision: str | None = "202603181030"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_review_feedback_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("predicted_category", sa.String(length=100), nullable=True),
        sa.Column("corrected_category", sa.String(length=100), nullable=False),
        sa.Column("prediction_confidence", sa.Float(), nullable=True),
        sa.Column("accepted_directly", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["item_id"], ["wardrobe_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_review_feedback_events_item_created_at",
        "ai_review_feedback_events",
        ["item_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_review_feedback_events_item_created_at",
        table_name="ai_review_feedback_events",
    )
    op.drop_table("ai_review_feedback_events")
