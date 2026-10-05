"""origen canonico_lista

Revision: 3f7b9e2d4c18
Anterior: 8a4d2f6c1b97
Fecha:    2026-10-04 12:00:00.000000+00:00

Por que este cambio: aprobar una lista ahora arma sus kits canonicos sin esperar
a que llegue el primer acudiente. El poller drena `lista_aprobada` del Catalogo
y crea un trabajo sin acudiente ni preferencias con `origen='canonico_lista'`,
que al terminar se publica sin avisar y fija el puntero de `kit_canonico`.

Va con `batch_alter_table`, como `origen_parent_apply`, porque SQLite no sabe
alterar un CHECK en sitio. En Postgres es un DROP + ADD normal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "3f7b9e2d4c18"
down_revision: str | None = "8a4d2f6c1b97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada', 'parent_apply')"
_NUEVO = (
    "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada', "
    "'parent_apply', 'canonico_lista')"
)


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_ANTERIOR))
