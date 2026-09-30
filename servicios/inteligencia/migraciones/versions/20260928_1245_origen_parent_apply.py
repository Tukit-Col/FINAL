"""origen parent_apply

Revision: 9a4b7c2e1d05
Anterior: 3d8f5a1c9e42
Fecha:    2026-09-28 12:45:00.000000+00:00

Por que este cambio: cuando un acudiente elige uno de los tres kits canonicos
de un grado, `aplicar-canonico` crea un trabajo que NO copia los kits: es un
puntero durable al trabajo canonico ya aprobado (`trabajos.aplicar_canonico`,
origen `parent_apply`). El valor ya estaba en el modelo (`modelos/trabajo.py`)
pero nunca llego a esta cadena de migraciones, asi que en una base creada antes
del cambio el CHECK de `origen` seguia sin admitirlo y el INSERT del puntero
violaba `trabajo_origen_valido`. Se agrega el valor, igual que se hizo con
`preview_onboarding` y `lista_verificada`.

Va con `batch_alter_table` porque SQLite no sabe alterar un CHECK en sitio:
recrea la tabla con la restriccion nueva. En Postgres es un DROP + ADD normal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "9a4b7c2e1d05"
down_revision: str | None = "3d8f5a1c9e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada')"
_NUEVO = (
    "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', "
    "'lista_verificada', 'parent_apply')"
)


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_ANTERIOR))
