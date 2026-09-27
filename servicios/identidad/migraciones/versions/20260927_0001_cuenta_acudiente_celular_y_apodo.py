"""cuenta del acudiente: celular del titular y apodo cifrado del hijo

Revision: a1b2c3d4e5f6
Anterior: 5c1a7e0d9b34
Fecha:    2026-09-27 00:01:00.000000+00:00

Por que este cambio: la cuenta del acudiente es ahora el primer paso de
/empezar. El titular aporta un celular para el aviso (hoy la API lo devuelve
None fijo), y cada hijo se refiere por un apodo. Ley 1581 / Anexo M: el nombre
del menor nunca se guarda en claro, y hasta el apodo va cifrado porque
singulariza al menor. `celular` va en claro (dato del adulto).
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5c1a7e0d9b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("celular", sa.String(length=32), nullable=True))
    op.add_column("acudiente_matricula", sa.Column("apodo_cifrado", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("acudiente_matricula", "apodo_cifrado")
    op.drop_column("usuario", "celular")
