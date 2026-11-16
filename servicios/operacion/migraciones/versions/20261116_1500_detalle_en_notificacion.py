"""asunto, detalle y dominio del destino en notificacion

Revision: a91c5e7d2b40
Anterior: 3f0bbbca4e60
Fecha:    2026-11-16 15:00:00.000000+00:00

Por que este cambio: el panel de correos enviados necesita ver que salio y que
paso. Hasta ahora la notificacion no guardaba el asunto ni el resultado del
envio (`Envio.detalle` se descartaba), asi que un correo que no llego no dejaba
rastro. Se agregan `asunto`, `detalle` (smtp, consola, destino_no_enviable,
smtp_error...) y `destino_dominio`: el dominio, nunca la direccion (Ley 1581).
Las columnas son nullable: las notificaciones de antes no las tienen.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "a91c5e7d2b40"
down_revision: str | None = "3f0bbbca4e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notificacion") as batch:
        batch.add_column(sa.Column("asunto", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("detalle", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("destino_dominio", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notificacion") as batch:
        batch.drop_column("destino_dominio")
        batch.drop_column("detalle")
        batch.drop_column("asunto")
