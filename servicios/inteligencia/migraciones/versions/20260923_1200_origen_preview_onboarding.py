"""origen preview_onboarding

Revision: 7b2c9e4a1f30
Anterior: fa6f12dd724e
Fecha:    2026-09-23 12:00:00.000000+00:00

Por que este cambio: la previsualizacion de kits de una lista recien subida
(`POST /v1/admin/onboarding/{version_id}/preview`) crea un trabajo desechable
con `origen='preview_onboarding'` para poder correr el pipeline lento (armar
los tres kits) ANTES de que el admin apruebe la version. El CHECK de `origen`
solo admitia `colegio_grado` y `archivo`, asi que insertar el trabajo de
previsualizacion violaba la restriccion. Se agrega el tercer valor.

Va con `batch_alter_table` porque SQLite no sabe alterar un CHECK en sitio:
recrea la tabla con la restriccion nueva. En Postgres es un DROP + ADD normal.
El resto de la definicion de la tabla se repite en el bloque batch porque
SQLite reconstruye la tabla entera y necesita conocerla completa.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "7b2c9e4a1f30"
down_revision: str | None = "fa6f12dd724e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "origen IN ('colegio_grado', 'archivo')"
_NUEVO = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_ANTERIOR))
