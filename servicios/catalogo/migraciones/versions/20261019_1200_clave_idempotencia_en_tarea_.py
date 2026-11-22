from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "3e7a1c9d5b62"
down_revision: str | None = "9f3c8d5b1a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("clave_idempotencia", sa.Uuid(), nullable=True))
    op.create_index("uq_tarea_clave_idempotencia", "tarea_importacion", ["clave_idempotencia"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_tarea_clave_idempotencia", table_name="tarea_importacion")
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("clave_idempotencia")
