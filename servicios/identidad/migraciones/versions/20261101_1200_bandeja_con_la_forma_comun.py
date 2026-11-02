"""bandeja de identidad con la forma comun

Revision: b7d4e1f20a93
Anterior: 6e2f9a4c1d83
Fecha:    2026-11-01 12:00:00.000000+00:00

Por que este cambio: la supresion del titular (Ley 1581) sale de Identidad por
evento hacia Comercio, Operacion e Inteligencia (ADR 0048). El publicador comun
(`tukit_comun.publicador`, ADR 0046) lee la bandeja con la forma que comparten
los demas servicios: `tipo`, `agregado_tipo`, `agregado_id`. La de Identidad
nacio como `tipo_evento` y `clave_agregado` (texto) y sin `agregado_tipo`, y
nadie la publicaba. Esta revision la alinea:

- `tipo_evento` pasa a llamarse `tipo`.
- `agregado_tipo` aparece; las filas viejas quedan como `usuario`.
- `clave_agregado` (texto) se vuelve `agregado_id` (uuid). Toda fila que ha
  escrito Identidad lleva ahi un id de usuario. Una que no se pueda leer como
  uuid hace fallar la revision, a proposito: es un evento que nadie sabria a
  quien atribuir.

El downgrade devuelve los nombres y el texto.
"""

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
        # SQLite guarda el uuid como 32 hex sin guiones; se devuelven con guiones.
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
