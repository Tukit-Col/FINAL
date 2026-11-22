from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "5c9e2a4f7b18"
down_revision: str | None = "3ac71d5e9b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("preferencias", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("preferencias")
