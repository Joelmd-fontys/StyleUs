"""Add image metadata and variant fields.

Revision ID: 202410291500
Revises: 202404031200
Create Date: 2024-10-29 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202410291500"
down_revision: str | None = "202404031200"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wardrobe_items",
        sa.Column("image_thumb_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_medium_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_width", sa.Integer(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_height", sa.Integer(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_mime_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column("image_checksum", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wardrobe_items", "image_checksum")
    op.drop_column("wardrobe_items", "image_mime_type")
    op.drop_column("wardrobe_items", "image_bytes")
    op.drop_column("wardrobe_items", "image_height")
    op.drop_column("wardrobe_items", "image_width")
    op.drop_column("wardrobe_items", "image_medium_url")
    op.drop_column("wardrobe_items", "image_thumb_url")
