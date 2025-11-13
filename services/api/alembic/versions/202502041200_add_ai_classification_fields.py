"""Add subcategory and ai confidence to wardrobe items."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202502041200"
down_revision: str | None = "202411010900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wardrobe_items", sa.Column("subcategory", sa.Text(), nullable=True))
    op.add_column("wardrobe_items", sa.Column("ai_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("wardrobe_items", "ai_confidence")
    op.drop_column("wardrobe_items", "subcategory")
