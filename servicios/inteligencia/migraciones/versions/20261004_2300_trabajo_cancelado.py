"""estado cancelado del trabajo

Revision: 9e3a5f7b2c41
Anterior: 7d4b2c9e1f36
Fecha:    2026-10-04 23:00:00.000000+00:00

Por que este cambio: el acudiente puede cancelar una solicitud (ADR 0031). El
trabajo pasa a `cancelado`, terminal, y deja de salir en "Mis solicitudes" y en
la cola de revision. Va con `batch_alter_table` porque SQLite no altera un CHECK
en sitio; en Postgres es un DROP + ADD normal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "9e3a5f7b2c41"
down_revision: str | None = "7d4b2c9e1f36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "estado IN ('encolado', 'procesando', 'espera_revision', 'publicado', 'fallido')"
_NUEVO = "estado IN ('encolado', 'procesando', 'espera_revision', 'publicado', 'fallido', 'cancelado')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_estado_valido", type_="check")
        batch.create_check_constraint("trabajo_estado_valido", sa.text(_NUEVO))


def downgrade() -> None:
    op.execute(
        "UPDATE trabajo_pipeline SET estado = 'fallido', error = 'cancelado' WHERE estado = 'cancelado'"
    )
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_estado_valido", type_="check")
        batch.create_check_constraint("trabajo_estado_valido", sa.text(_ANTERIOR))
