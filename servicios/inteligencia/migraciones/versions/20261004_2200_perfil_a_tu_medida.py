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
