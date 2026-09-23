"""evidencia de onboarding en tarea_importacion

Revision: 0f882b23c8ad
Anterior: 4b1c8a2f6d33
Fecha:    2026-09-23 05:05:05.849301+00:00

Por que este cambio: el onboarding percibe un PDF y escribe la lista, pero sin
guardar el PDF ni lo que la percepcion leyo, el administrador curaria a ciegas
—no habria contra que cotejar los renglones. Estas columnas guardan la
evidencia en la propia tarea de importacion (documento + percepcion cruda) y
la atan a la version que produjo, para que la revision tenga la fuente a la
vista y la promesa de fidelidad al documento del colegio sea verificable.
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

revision: str = "0f882b23c8ad"
down_revision: str | None = "4b1c8a2f6d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Se usa batch_alter_table y no ALTER a pelo por la FK de `version_id`:
    # Postgres agrega la restriccion con un ADD CONSTRAINT, pero SQLite no
    # soporta ALTER de constraints, y esta migracion se prueba tambien contra
    # SQLite (Postgres esta abajo). Batch es el camino que Alembic da para eso:
    # en SQLite recrea la tabla por copia-y-mueve, en Postgres emite ALTERs
    # normales. Las columnas planas y la FK con ON DELETE SET NULL quedan igual
    # en los dos motores.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("documento", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("percepcion_cruda", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("version_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("colegio_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("grado", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("anio_lectivo", sa.SmallInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_tarea_importacion_version_id",
            "version_lista_oficial",
            ["version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_constraint("fk_tarea_importacion_version_id", type_="foreignkey")
        batch.drop_column("anio_lectivo")
        batch.drop_column("grado")
        batch.drop_column("colegio_id")
        batch.drop_column("version_id")
        batch.drop_column("percepcion_cruda")
        batch.drop_column("documento")
