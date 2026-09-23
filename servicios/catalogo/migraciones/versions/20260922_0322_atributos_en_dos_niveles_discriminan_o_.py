"""atributos en dos niveles: discriminan o solo describen

Revision: 4b1c8a2f6d33
Anterior: 79d641af049e
Fecha:    2026-09-22 03:22:00.000000+00:00

Por que este cambio: `atributos_requeridos` cumplia dos papeles a la vez y
eso obligaba a elegir entre dos males. Medido contra las 4.719 lineas del
corpus, de 155 pares concepto-atributo solo 81 los pide alguna lista. Usados
todos como restriccion dura, pedir `bata blanca de laboratorio` no resuelve
nada porque ninguna bata del catalogo declara su `talla` y se descartan todas;
ignorados todos, se pierde `rayado`, que 353 lineas especifican y que decide
si un cuaderno sirve.

La columna se RENOMBRA en vez de crearse y borrarse, que es lo que proponia el
autogenerate: crear y borrar perderia lo que ya hay. Tras la migracion todo
queda como discriminante, que es el estado actual, y el reparto medido lo
aplica el cargador desde `conceptos.csv`, donde es reproducible.
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
from sqlalchemy.dialects import postgresql

revision: str = "4b1c8a2f6d33"
down_revision: str | None = "79d641af049e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LISTA = sa.JSON().with_variant(postgresql.ARRAY(sa.String()), "postgresql")


def upgrade() -> None:
    op.alter_column("concepto", "atributos_requeridos", new_column_name="atributos_discriminantes")
    op.add_column(
        "concepto",
        sa.Column("atributos_descriptivos", _LISTA, nullable=False, server_default="{}"),
    )
    op.alter_column("concepto", "atributos_descriptivos", server_default=None)

    # El mismo invariante que valida el modelo. Hace falta declararlo aqui
    # porque la DDL condicionada del modelo solo corre con `create_all`, y una
    # base que nacio de migraciones no pasa por ahi: sin esto, el entorno de
    # desarrollo tendria el CHECK y produccion no.
    op.create_check_constraint(
        "concepto_atributos_sin_solapar",
        "concepto",
        "NOT (atributos_discriminantes && atributos_descriptivos)",
    )


def downgrade() -> None:
    op.drop_constraint("concepto_atributos_sin_solapar", "concepto", type_="check")
    # Al volver atras los dos papeles se juntan otra vez, asi que lo que solo
    # describia vuelve a ser exigido. Se conserva en vez de tirarse: perder
    # que atributos declaraba un concepto es peor que exigirlos de mas.
    op.execute(
        "UPDATE concepto SET atributos_discriminantes = atributos_discriminantes || atributos_descriptivos"
    )
    op.drop_column("concepto", "atributos_descriptivos")
    op.alter_column("concepto", "atributos_discriminantes", new_column_name="atributos_requeridos")
