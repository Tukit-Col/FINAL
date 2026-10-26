"""los canonicos que eran el kit de un papa vuelven a su lista

Revision: 8b2e4d6f0a13
Anterior: 3c7d9e1f5a28
Fecha:    2026-10-25 12:00:00.000000+00:00

Por que este cambio: hasta ahora, aprobar en la cola de revision el trabajo de
un acudiente lo fijaba ademas como kit canonico de su grado, y los papas
siguientes recibian por la ruta rapida un kit armado con el presupuesto, la
prioridad o el personaje de otro. Desde que aprobar solo publica, el canonico
sale de la lista aprobada (`canonico_lista`) o de un preview fijado. Esta
migracion arregla los punteros que quedaron de antes: cada grado que apunta al
trabajo de un papa pasa al ultimo `canonico_lista` publicado de su (colegio,
grado, anio). Un grado sin canonico de lista se queda como esta: quitarle el
puntero lo dejaria sin ruta rapida.

No hay downgrade de datos: el puntero viejo era justamente el defecto, y no se
guarda a que trabajo apuntaba.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "8b2e4d6f0a13"
down_revision: str | None = "3c7d9e1f5a28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los origenes que SI son canonicos: sin acudiente ni preferencias.
_SIN_ACUDIENTE = ("canonico_lista", "preview_onboarding")
_ORIGEN_LISTA = "canonico_lista"
# El anio bajo el que se arma un kit cuyo hijo no lo trajo (`trabajos.py`).
_ANIO_POR_OMISION = 2026

_TRABAJO = sa.table(
    "trabajo_pipeline",
    sa.column("id", sa.Uuid()),
    sa.column("estado", sa.String()),
    sa.column("origen", sa.String()),
    sa.column("hijos", sa.JSON().with_variant(JSONB(), "postgresql")),
    sa.column("terminado_en", sa.DateTime(timezone=True)),
)
_CANONICO = sa.table(
    "kit_canonico",
    sa.column("id", sa.Uuid()),
    sa.column("colegio_id", sa.String()),
    sa.column("grado", sa.String()),
    sa.column("anio_lectivo", sa.Integer()),
    sa.column("trabajo_id", sa.Uuid()),
    sa.column("actualizado_en", sa.DateTime(timezone=True)),
)


def _grado_de(hijos: object) -> tuple[str, str, int] | None:
    if not isinstance(hijos, list) or len(hijos) != 1 or not isinstance(hijos[0], dict):
        return None
    hijo = hijos[0]
    colegio, grado = str(hijo.get("colegio_id") or ""), str(hijo.get("grado") or "")
    if not (colegio and grado):
        return None
    return colegio, grado, int(hijo.get("anio_lectivo") or _ANIO_POR_OMISION)


def upgrade() -> None:
    conexion = op.get_bind()
    de_papa = conexion.execute(
        sa.select(_CANONICO.c.id, _CANONICO.c.colegio_id, _CANONICO.c.grado, _CANONICO.c.anio_lectivo)
        .select_from(_CANONICO.join(_TRABAJO, _TRABAJO.c.id == _CANONICO.c.trabajo_id))
        .where(_TRABAJO.c.origen.not_in(_SIN_ACUDIENTE))
    ).all()
    if not de_papa:
        return

    # El ultimo canonico de lista publicado por (colegio, grado, anio). Los
    # `hijos` se leen en Python para que la migracion sea la misma en Postgres
    # y en SQLite; son pocos trabajos (uno por cada vez que se aprobo una lista).
    def _orden(fila: sa.Row) -> tuple[float, str]:
        # Sin `terminado_en` va de ultimo; el id desempata para que sea estable.
        return (fila.terminado_en.timestamp() if fila.terminado_en else 0.0, str(fila.id))

    ultimo: dict[tuple[str, str, int], sa.Row] = {}
    for fila in conexion.execute(
        sa.select(_TRABAJO.c.id, _TRABAJO.c.hijos, _TRABAJO.c.terminado_en).where(
            _TRABAJO.c.origen == _ORIGEN_LISTA, _TRABAJO.c.estado == "publicado"
        )
    ):
        llave = _grado_de(fila.hijos)
        if llave is not None and (llave not in ultimo or _orden(fila) > _orden(ultimo[llave])):
            ultimo[llave] = fila

    for puntero in de_papa:
        destino = ultimo.get((puntero.colegio_id, puntero.grado, int(puntero.anio_lectivo)))
        if destino is None:
            continue
        conexion.execute(
            sa.update(_CANONICO)
            .where(_CANONICO.c.id == puntero.id)
            .values(trabajo_id=destino.id, actualizado_en=sa.func.now())
        )


def downgrade() -> None:
    pass
