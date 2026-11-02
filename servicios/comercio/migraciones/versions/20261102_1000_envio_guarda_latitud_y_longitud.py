"""envio guarda latitud y longitud

Revision: c7a41e9d02f5
Anterior: b619c58fc0c3
Fecha:    2026-11-02 10:00:00.000000+00:00

Por que este cambio: sin llave de Google, el checkout deja que el acudiente
busque su direccion en OpenStreetMap y la confirme moviendo un pin en un mapa
(ADR 0049). El punto confirmado se guarda en el envio para que logistica abra
el lugar exacto y pueda agrupar el reparto. La licencia de OSM (ODbL) si
permite guardar coordenadas; la de Google no, por eso el ADR 0044 las
descartaba. Nullable: los pedidos ya escritos, las direcciones a mano y las
elegidas por Google no las tienen.
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

revision: str = "c7a41e9d02f5"
down_revision: str | None = "b619c58fc0c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("envio", sa.Column("latitud", sa.Float(), nullable=True))
    op.add_column("envio", sa.Column("longitud", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "longitud")
    op.drop_column("envio", "latitud")
