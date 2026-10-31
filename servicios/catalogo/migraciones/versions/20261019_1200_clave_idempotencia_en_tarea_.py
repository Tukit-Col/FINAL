"""clave_idempotencia en tarea_importacion

Revision: 3e7a1c9d5b62
Anterior: 9f3c8d5b1a24
Fecha:    2026-10-19 12:00:00.000000+00:00

Por que este cambio: con el catalogo caido, la subida de un acudiente ya no se
pierde; inteligencia la guarda y la importa cuando el catalogo vuelve (H-B-01,
ADR 0040). Ese reintento solo es seguro si el catalogo reconoce una importacion
que ya entro: si un intento llego pero su respuesta se perdio, el siguiente trae
la misma `clave_idempotencia` y recibe la version que ya existe en vez de crear
otra. La columna es unica y nullable: el onboarding de administrador y las
tareas de antes no traen clave, y el indice unico admite varios NULL en los dos
motores.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "3e7a1c9d5b62"
down_revision: str | None = "9f3c8d5b1a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table por la FK preexistente de `version_id`: SQLite no
    # soporta ALTER de constraints y esta migracion se prueba tambien contra
    # SQLite.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("clave_idempotencia", sa.Uuid(), nullable=True))
    op.create_index("uq_tarea_clave_idempotencia", "tarea_importacion", ["clave_idempotencia"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_tarea_clave_idempotencia", table_name="tarea_importacion")
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("clave_idempotencia")
