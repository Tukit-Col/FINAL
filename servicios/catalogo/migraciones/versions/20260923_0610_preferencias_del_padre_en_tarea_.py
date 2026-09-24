"""preferencias del padre en tarea_importacion

Revision: 5c9e2a4f7b18
Anterior: 3ac71d5e9b02
Fecha:    2026-09-23 06:10:00.000000+00:00

Por que este cambio: cuando un acudiente sube su lista, declara sus
preferencias (paso 3 del formulario: pesos, disposicion a pagar de mas,
personaje por hijo). Pero su kit NO se arma al subir —la lista entra sin
revisar— sino cuando un administrador la aprueba. Entre esos dos momentos las
preferencias tienen que sobrevivir en algun lado, y este es el lugar natural:
la misma fila que ya guarda la traza al padre (`contacto_referencia`). Al
aprobar, un trabajo de ruta rapida las lee para optimizar los tres kits a la
medida de lo que el padre pidio, en vez de con los pesos por omision. Es dato
de negocio (no PII): no lleva correo ni telefono. Nullable porque el
onboarding del colegio no trae padre ni preferencias.
"""

from __future__ import annotations

from collections.abc import Sequence

# `Vector` no es un tipo de SQLAlchemy sino de pgvector, asi que Alembic lo
# emite con el nombre completo y hace falta tenerlo importado. Se deja siempre,
# aunque la revision no lo use: que falte es un fallo en tiempo de migracion,
# que sobre no cuesta nada.
import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
# que solo corren SQL a mano, o las de datos. Quitarlos de la plantilla
# obligaria a reponerlos a mano en las demas, que son la mayoria.
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "5c9e2a4f7b18"
down_revision: str | None = "3ac71d5e9b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table y no ALTER a pelo por la FK preexistente de `version_id`:
    # SQLite no soporta ALTER de constraints y esta migracion se prueba tambien
    # contra SQLite (Postgres esta abajo). En SQLite Batch recrea la tabla por
    # copia-y-mueve; en Postgres emite un ALTER normal. La columna es JSON y
    # nullable, asi que queda igual en los dos motores.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("preferencias", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("preferencias")
