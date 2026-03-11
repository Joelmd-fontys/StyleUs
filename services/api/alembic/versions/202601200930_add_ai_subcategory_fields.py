"""Reintroduce subcategory and AI attribute fields."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202601200930"
down_revision: str | None = "202512181000"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.add_column(sa.Column("subcategory", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("ai_materials", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ai_style_tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.drop_column("ai_style_tags")
        batch_op.drop_column("ai_materials")
        batch_op.drop_column("subcategory")
