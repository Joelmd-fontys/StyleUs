"""Add durable AI job result payload."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202603111200"
down_revision: str | None = "202603111100"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.add_column(sa.Column("result_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_column("result_payload")
