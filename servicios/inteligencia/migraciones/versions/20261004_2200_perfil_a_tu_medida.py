"""perfil A tu Medida

Revision: 7d4b2c9e1f36
Anterior: 5c1e8a3f9b20
Fecha:    2026-10-04 22:00:00.000000+00:00

Por que este cambio: el kit del punto medio deja de ser un Premium ajustado y
pasa a ser un kit propio, `A tu Medida` (ADR 0030). El CHECK de `kit.perfil`
tiene que admitirlo. Va con `batch_alter_table` porque SQLite no altera un
CHECK en sitio; en Postgres es un DROP + ADD normal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "7d4b2c9e1f36"
down_revision: str | None = "5c1e8a3f9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "perfil IN ('Ahorrador', 'Fan', 'Premium')"
_NUEVO = "perfil IN ('Ahorrador', 'Fan', 'A tu Medida', 'Premium')"


def upgrade() -> None:
    with op.batch_alter_table("kit") as batch:
        batch.drop_constraint("kit_perfil_valido", type_="check")
        batch.create_check_constraint("kit_perfil_valido", sa.text(_NUEVO))


def downgrade() -> None:
    op.execute("DELETE FROM kit WHERE perfil = 'A tu Medida'")
    with op.batch_alter_table("kit") as batch:
        batch.drop_constraint("kit_perfil_valido", type_="check")
        batch.create_check_constraint("kit_perfil_valido", sa.text(_ANTERIOR))
