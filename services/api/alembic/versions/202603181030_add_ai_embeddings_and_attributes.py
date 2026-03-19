"""Add AI embedding and attribute fields to wardrobe items."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202603181030"
down_revision: str | None = "202603111200"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.add_column(sa.Column("ai_attribute_tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ai_embedding", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ai_embedding_model", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.drop_column("ai_embedding_model")
        batch_op.drop_column("ai_embedding")
        batch_op.drop_column("ai_attribute_tags")
