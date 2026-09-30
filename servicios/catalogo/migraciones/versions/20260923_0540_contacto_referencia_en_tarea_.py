"""contacto de referencia en tarea_importacion

Revision: 3ac71d5e9b02
Anterior: 0f882b23c8ad
Fecha:    2026-09-23 05:40:00.000000+00:00

Por que este cambio: un padre cuyo (colegio, grado) no tiene lista verificada
puede sugerir su lista al backlog del administrador. Esa sugerencia debe poder
rastrearse hasta el acudiente que la envio —para pedirle el original si hace
falta— pero SIN guardar su correo ni su telefono: el dato de contacto (PII)
vive solo en Identidad. Esta columna referencia al acudiente por su
identificador (`contacto_referencia`, el `usuario_id` que Identidad ya emite),
nunca por correo. Asi la traza existe y la PII no se duplica en Catalogo.
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

revision: str = "3ac71d5e9b02"
down_revision: str | None = "0f882b23c8ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table y no ALTER a pelo por la FK preexistente de `version_id`:
    # SQLite no soporta ALTER de constraints y esta migracion se prueba tambien
    # contra SQLite (Postgres esta abajo). En SQLite Batch recrea la tabla por
    # copia-y-mueve; en Postgres emite un ALTER normal. La columna es plana y
    # nullable, asi que queda igual en los dos motores.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("contacto_referencia", sa.Uuid(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("contacto_referencia")
