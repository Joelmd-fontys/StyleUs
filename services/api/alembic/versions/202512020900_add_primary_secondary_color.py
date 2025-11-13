"""Add primary and secondary color columns."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202512020900"
down_revision: str | None = "202511011000"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wardrobe_items",
        sa.Column("primary_color", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("secondary_color", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wardrobe_items", "secondary_color")
    op.drop_column("wardrobe_items", "primary_color")
