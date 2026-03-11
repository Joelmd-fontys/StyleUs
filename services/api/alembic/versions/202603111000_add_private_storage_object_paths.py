"""Add private storage object path columns for wardrobe media."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202603111000"
down_revision: str | None = "202601200930"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.add_column(sa.Column("image_object_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("image_thumb_object_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("image_medium_object_path", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wardrobe_items") as batch_op:
        batch_op.drop_column("image_medium_object_path")
        batch_op.drop_column("image_thumb_object_path")
        batch_op.drop_column("image_object_path")
