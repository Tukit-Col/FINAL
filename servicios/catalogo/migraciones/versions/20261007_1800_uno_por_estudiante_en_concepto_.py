"""uno_por_estudiante en concepto

Revision: 8e2b7c4a9f13
Anterior: 6d1a3f8c2e94
Fecha:    2026-10-07 18:00:00.000000+00:00

Por que este cambio: las listas se escriben por materia, y cada profesor pide
lo que usa. Las tijeras salen en artes, en tecnologia y en la cartuchera; son
las mismas tijeras y el kit cobraba tres. En las 18 listas curadas, 43
renglones de herramientas repetian a otro identico. Lo que distingue a esas
herramientas de lo que se gasta (pegante, cinta, cuadernos, que si pueden ser
uno por materia) es una propiedad del CONCEPTO, no del renglon: una regla dura
todo el ano y sirve en todas las clases. Booleana y con valor por omision
falso, para que ningun concepto existente cambie de comportamiento sin que
alguien lo marque.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "8e2b7c4a9f13"
down_revision: str | None = "6d1a3f8c2e94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("concepto") as batch:
        batch.add_column(
            sa.Column("uno_por_estudiante", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("concepto") as batch:
        batch.drop_column("uno_por_estudiante")
