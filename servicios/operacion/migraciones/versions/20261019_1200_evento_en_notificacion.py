"""evento de bandeja en notificacion

Revision: 3f0bbbca4e60
Anterior: d0bf03671b97
Fecha:    2026-10-19 12:00:00.000000+00:00

Por que este cambio: un solo pago avisaba dos veces `pedido_pagado` (H-B-03,
ADR 0042). El repartidor envia y registra la notificacion antes de que la
bandeja de origen marque y publique el evento; si publicar falla, la bandeja
vuelve atras y el evento llega otra vez. Ahora la notificacion guarda de que
evento sale (`evento_origen`, `evento_id`) y el repartidor no vuelve a avisar uno
que ya tiene su aviso `enviada`. El indice unico es PARCIAL (`estado =
'enviada'`): un evento puede tener varios intentos `fallida` antes del que sale.
Las columnas son nullable: las notificaciones de antes no tienen evento, y el
indice admite varios NULL en los dos motores. Va en el modelo y aqui, no en
`infra/postgres/indices`: es parte del esquema, y un `CREATE UNIQUE INDEX` alli
saldria como deriva falsa (H-A-05).
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "3f0bbbca4e60"
down_revision: str | None = "d0bf03671b97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOLO_ENVIADAS = sa.text("estado = 'enviada'")


def upgrade() -> None:
    # batch_alter_table para que el downgrade (y esta subida) corran tambien
    # contra SQLite, donde se prueba la migracion.
    with op.batch_alter_table("notificacion") as batch:
        batch.add_column(sa.Column("evento_origen", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("evento_id", sa.BigInteger(), nullable=True))
    op.create_index(
        "uq_notificacion_evento_enviada",
        "notificacion",
        ["evento_origen", "evento_id"],
        unique=True,
        postgresql_where=_SOLO_ENVIADAS,
        sqlite_where=_SOLO_ENVIADAS,
    )


def downgrade() -> None:
    op.drop_index("uq_notificacion_evento_enviada", table_name="notificacion")
    with op.batch_alter_table("notificacion") as batch:
        batch.drop_column("evento_id")
        batch.drop_column("evento_origen")
