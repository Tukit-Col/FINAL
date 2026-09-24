"""colegio_datos en tarea_importacion

Revision: 6d1a3f8c2e94
Anterior: 5c9e2a4f7b18
Fecha:    2026-09-23 07:00:00.000000+00:00

Por que este cambio: cuando un acudiente sube su lista para un colegio que
TODAVIA NO EXISTE en Tukit —lo eligio del directorio de Bogota (trae DANE) o lo
escribio a mano (solo nombre)— hay que guardar en algun lado con que crear ese
colegio al aprobar. La version de la lista se importa igual (su `colegio_id` se
deriva de forma estable del DANE o del nombre normalizado), pero el nombre, el
DANE y los atributos que el revisor completa antes de aprobar (logo, direccion,
contacto) no caben en la lista: son del COLEGIO, no de la lista. Viven en la
misma fila que ya guarda la traza al padre, y son lo unico que Tukit sabe del
colegio hasta que la aprobacion emite el evento que Identidad consume para
crearlo. Nullable porque un colegio aliado ya conocido, o el onboarding de
administrador, no traen datos de colegio que crear.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "6d1a3f8c2e94"
down_revision: str | None = "5c9e2a4f7b18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table por la FK preexistente de `version_id`: SQLite no
    # soporta ALTER de constraints y esta migracion se prueba tambien contra
    # SQLite. La columna es JSON y nullable, asi que queda igual en los dos
    # motores.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("colegio_datos", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("colegio_datos")
