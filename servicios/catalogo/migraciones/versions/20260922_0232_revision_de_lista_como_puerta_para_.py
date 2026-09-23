"""revision de lista como puerta para buscar afuera

Revision: 79d641af049e
Anterior: 7c679f269235
Fecha:    2026-09-22 02:32:05.806115+00:00

Por que este cambio: el match de una lista corre siempre contra nuestro
catalogo. Salir a una tienda es un acto de ALTA, no de consulta, y necesita
una puerta que diga cuando esta permitido. Esa puerta es una version de lista
todavia sin revisar: `version_lista_oficial.revisada_en` la cierra, y cada
propuesta queda atada a la version y al renglon que la pidio para que el
permiso tenga dueño. `origen` distingue lo que trajo el scraper de lo que
escribio una persona, que es el camino normal de los libros.
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

revision: str = "79d641af049e"
down_revision: str | None = "7c679f269235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La puerta. Nulo quiere decir "sin revisar", y es el unico estado en que
    # el catalogo puede consultar una tienda o admitir un alta a mano.
    op.add_column(
        "version_lista_oficial", sa.Column("revisada_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("version_lista_oficial", sa.Column("revisada_por", sa.Uuid(), nullable=True))

    # De donde salio cada propuesta. Las filas que ya existen se marcan
    # 'scraper' porque es de donde vinieron; el server_default se retira
    # enseguida para que quien inserte tenga que decirlo.
    op.add_column(
        "propuesta_producto",
        sa.Column("origen", sa.String(length=16), nullable=False, server_default="scraper"),
    )
    op.alter_column("propuesta_producto", "origen", server_default=None)
    op.create_check_constraint(
        "propuesta_origen_valido", "propuesta_producto", "origen IN ('scraper', 'manual')"
    )

    # El vinculo con la revision que la pidio. Admite nulo por las filas que
    # ya estan, sembradas antes de que existiera la puerta.
    op.add_column("propuesta_producto", sa.Column("version_lista_id", sa.Uuid(), nullable=True))
    op.add_column("propuesta_producto", sa.Column("item_lista_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_propuesta_version_lista",
        "propuesta_producto",
        "version_lista_oficial",
        ["version_lista_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_propuesta_item_lista",
        "propuesta_producto",
        "item_lista_oficial",
        ["item_lista_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Los indices HNSW y GIN de `producto_canonico` los aplica la
    # infraestructura (bd/init), no el modelo, asi que el autogenerate los ve
    # como sobrantes y propone borrarlos. Se quitan del diff a mano: borrarlos
    # aqui dejaria la busqueda hibrida recorriendo la tabla entera sin que
    # ninguna prueba se queje.


def downgrade() -> None:
    op.drop_constraint("fk_propuesta_item_lista", "propuesta_producto", type_="foreignkey")
    op.drop_constraint("fk_propuesta_version_lista", "propuesta_producto", type_="foreignkey")
    op.drop_column("propuesta_producto", "item_lista_id")
    op.drop_column("propuesta_producto", "version_lista_id")
    op.drop_constraint("propuesta_origen_valido", "propuesta_producto", type_="check")
    op.drop_column("propuesta_producto", "origen")
    op.drop_column("version_lista_oficial", "revisada_por")
    op.drop_column("version_lista_oficial", "revisada_en")
