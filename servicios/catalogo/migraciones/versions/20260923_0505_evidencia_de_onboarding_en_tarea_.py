from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "0f882b23c8ad"
down_revision: str | None = "4b1c8a2f6d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("documento", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("percepcion_cruda", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("version_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("colegio_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("grado", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("anio_lectivo", sa.SmallInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_tarea_importacion_version_id",
            "version_lista_oficial",
            ["version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_constraint("fk_tarea_importacion_version_id", type_="foreignkey")
        batch.drop_column("anio_lectivo")
        batch.drop_column("grado")
        batch.drop_column("colegio_id")
        batch.drop_column("version_id")
        batch.drop_column("percepcion_cruda")
        batch.drop_column("documento")
