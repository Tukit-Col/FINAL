from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e1f20a93"
down_revision: str | None = "6e2f9a4c1d83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _es_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    with op.batch_alter_table("bandeja_salida") as tabla:
        tabla.alter_column("tipo_evento", new_column_name="tipo", existing_type=sa.String(128))
        tabla.add_column(sa.Column("agregado_tipo", sa.String(64), nullable=False, server_default="usuario"))
        tabla.add_column(sa.Column("agregado_id", sa.Uuid(), nullable=True))
    if _es_postgres():
        op.execute("UPDATE bandeja_salida SET agregado_id = clave_agregado::uuid")
    else:
        op.execute("UPDATE bandeja_salida SET agregado_id = REPLACE(clave_agregado, '-', '')")
    with op.batch_alter_table("bandeja_salida") as tabla:
        tabla.alter_column("agregado_tipo", server_default=None, existing_type=sa.String(64))
        tabla.alter_column("agregado_id", nullable=False, existing_type=sa.Uuid())
        tabla.drop_column("clave_agregado")


def downgrade() -> None:
    with op.batch_alter_table("bandeja_salida") as tabla:
        tabla.add_column(sa.Column("clave_agregado", sa.String(128), nullable=True))
    if _es_postgres():
        op.execute("UPDATE bandeja_salida SET clave_agregado = agregado_id::text")
    else:
        op.execute(
            "UPDATE bandeja_salida SET clave_agregado = lower("
            "substr(agregado_id, 1, 8) || '-' || substr(agregado_id, 9, 4) || '-' || "
            "substr(agregado_id, 13, 4) || '-' || substr(agregado_id, 17, 4) || '-' || "
            "substr(agregado_id, 21))"
        )
    with op.batch_alter_table("bandeja_salida") as tabla:
        tabla.alter_column("clave_agregado", nullable=False, existing_type=sa.String(128))
        tabla.drop_column("agregado_id")
        tabla.drop_column("agregado_tipo")
        tabla.alter_column("tipo", new_column_name="tipo_evento", existing_type=sa.String(128))
