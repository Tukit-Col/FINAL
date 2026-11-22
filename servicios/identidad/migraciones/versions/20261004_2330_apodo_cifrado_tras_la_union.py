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
    pass
