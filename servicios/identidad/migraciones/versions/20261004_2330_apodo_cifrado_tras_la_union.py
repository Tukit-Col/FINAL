"""apodo cifrado tras la union con main

Revision: 6e2f9a4c1d83
Anterior: 54f1601a17c5
Fecha:    2026-10-04 23:30:00.000000+00:00

Por que este cambio: antes de unir las ramas habia dos caminos a
`54f1601a17c5`. El de main pasa por `a1b2c3d4e5f6`, que agrega `usuario.celular`
y `acudiente_matricula.apodo_cifrado`. El de la rama de integracion pasaba por
`618057ff65e1`, que solo agregaba `celular`. La cadena unida se queda con la de
main, pero una base que ya llego a `54f1601a17c5` por el otro camino no tiene
`apodo_cifrado`, y Alembic no lo nota porque la revision actual es la misma.

Esta revision lo pone si falta, y tambien `celular` por si acaso. En una base
que siguio la cadena de main no hace nada.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "6e2f9a4c1d83"
down_revision: str | None = "54f1601a17c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columnas(tabla: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabla)}


def upgrade() -> None:
    if "celular" not in _columnas("usuario"):
        op.add_column("usuario", sa.Column("celular", sa.String(length=32), nullable=True))
    if "apodo_cifrado" not in _columnas("acudiente_matricula"):
        op.add_column("acudiente_matricula", sa.Column("apodo_cifrado", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    # Las columnas son de `a1b2c3d4e5f6`; quitarlas le toca a esa revision.
    pass
