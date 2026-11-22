from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "3ac71d5e9b02"
down_revision: str | None = "0f882b23c8ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("contacto_referencia", sa.Uuid(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("contacto_referencia")
