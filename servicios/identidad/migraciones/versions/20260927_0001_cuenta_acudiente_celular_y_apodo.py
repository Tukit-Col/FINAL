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
