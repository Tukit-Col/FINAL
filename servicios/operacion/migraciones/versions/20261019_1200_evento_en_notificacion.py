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
