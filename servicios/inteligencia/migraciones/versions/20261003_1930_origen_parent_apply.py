"""origen parent_apply

Revision: 8a4d2f6c1b97
Anterior: 5c1e8b7d2a64
Fecha:    2026-10-03 19:30:00.000000+00:00

Por que este cambio: la ruta rapida de `/empezar` (`POST /v1/trabajos/aplicar-canonico`)
arma el kit del padre a partir del kit canonico de su colegio y grado, y ese
trabajo nace con `origen='parent_apply'`. El modelo lo admite desde el commit
4b495f9 (2026-09-25), pero ninguna migracion lo llevo a la base, asi que el
CHECK de Postgres rechazaba el INSERT y el acudiente veia "El backend respondio
500". Es el mismo hueco que `tabla_kit_canonico`, del mismo commit.

`make bd-deriva` no lo detecto porque la comparacion de Alembic no mira las
restricciones CHECK: modelo y base decian cosas distintas y el detector
reportaba "sin deriva".

Va con `batch_alter_table`, como `origen_lista_verificada`, porque SQLite no
sabe alterar un CHECK en sitio. En Postgres es un DROP + ADD normal.

Al unir con main: alli el mismo arreglo llego como `9a4b7c2e1d05`, que ahora va
ANTES en la cadena. Esta revision se conserva porque las bases que siguieron
esta rama ya la tienen aplicada; su upgrade reafirma el mismo CHECK (no cambia
nada) y su downgrade no lo toca, porque quitar `parent_apply` le toca a
`9a4b7c2e1d05`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "8a4d2f6c1b97"
down_revision: str | None = "5c1e8b7d2a64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NUEVO = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada', 'parent_apply')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    # `parent_apply` lo agrego `9a4b7c2e1d05`, que queda debajo: se deja.
    pass
