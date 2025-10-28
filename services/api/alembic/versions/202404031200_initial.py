"""Initial schema.

Revision ID: 202404031200
Revises: 
Create Date: 2024-04-03 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.db.types import GUID


revision: str = "202404031200"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "wardrobe_items",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "item_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", GUID(), sa.ForeignKey("wardrobe_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
    )

    op.create_index("ix_wardrobe_items_category", "wardrobe_items", ["category"])

    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_wardrobe_items_user_created_at ON wardrobe_items (user_id, created_at DESC)"
        )
    else:
        op.create_index(
            "ix_wardrobe_items_user_created_at",
            "wardrobe_items",
            ["user_id", "created_at"],
        )

    op.create_index("ix_item_tags_tag", "item_tags", ["tag"])


def downgrade() -> None:
    op.drop_index("ix_item_tags_tag", table_name="item_tags")
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_wardrobe_items_user_created_at")
    else:
        op.drop_index("ix_wardrobe_items_user_created_at", table_name="wardrobe_items")
    op.drop_index("ix_wardrobe_items_category", table_name="wardrobe_items")
    op.drop_table("item_tags")
    op.drop_table("wardrobe_items")
    op.drop_table("users")
