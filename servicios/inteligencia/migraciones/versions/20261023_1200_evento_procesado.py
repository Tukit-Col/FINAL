"""tabla evento_procesado

Revision: 3c7d9e1f5a28
Anterior: 6a2f8c4e1d57
Fecha:    2026-10-23 12:00:00.000000+00:00

Por que este cambio: con RabbitMQ (ADR 0046) el sondeador de listas recibe sus
eventos por la cola `inteligencia.listas`, y la entrega es al menos una vez. Un
`lista_verificada` repetido creaba otro trabajo y otro kit para el mismo padre.
Esta tabla guarda los eventos ya procesados por origen e id; la marca entra en
la misma transaccion que crea el trabajo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c7d9e1f5a28"
down_revision: str | None = "6a2f8c4e1d57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evento_procesado",
        sa.Column("origen", sa.String(length=32), nullable=False),
        sa.Column("evento_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("origen", "evento_id"),
    )


def downgrade() -> None:
    op.drop_table("evento_procesado")
