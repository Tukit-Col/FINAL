"""origen lista_verificada

Revision: 3d8f5a1c9e42
Anterior: 7b2c9e4a1f30
Fecha:    2026-09-23 18:30:00.000000+00:00

Por que este cambio: cuando un administrador aprueba la version que un padre
subio, el Catalogo escribe `lista_verificada` en su bandeja de salida y un
poller de este servicio la drena para armar el kit de RUTA RAPIDA de ese padre
(`poller.py`). Ese trabajo nace con `origen='lista_verificada'` para
distinguirlo de la subida directa (`colegio_grado`) y de la previsualizacion
del admin (`preview_onboarding`). El CHECK de `origen` no lo admitia, asi que
insertar el trabajo del poller violaba la restriccion. Se agrega el valor.

Va con `batch_alter_table` porque SQLite no sabe alterar un CHECK en sitio:
recrea la tabla con la restriccion nueva. En Postgres es un DROP + ADD normal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "3d8f5a1c9e42"
down_revision: str | None = "7b2c9e4a1f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding')"
_NUEVO = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_ANTERIOR))
